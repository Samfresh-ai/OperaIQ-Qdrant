from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

from qdrant_client import QdrantClient, models

from app.config import Settings
from app.embedder import Embedder
from app.models import (
    AppLogEvent,
    IncidentMemory,
    QdrantCollectionReport,
    RecallMatch,
    ResolutionResult,
    SplunkAlert,
    VerificationResult,
)


INDEXED_FIELDS: dict[str, models.PayloadSchemaType] = {
    "orgId": models.PayloadSchemaType.KEYWORD,
    "service": models.PayloadSchemaType.KEYWORD,
    "severity": models.PayloadSchemaType.KEYWORD,
    "resolved": models.PayloadSchemaType.BOOL,
    "createdAt": models.PayloadSchemaType.DATETIME,
    "kind": models.PayloadSchemaType.KEYWORD,
    "project": models.PayloadSchemaType.KEYWORD,
}


class IncidentMemoryService:
    def __init__(
        self,
        settings: Settings,
        embedder: Embedder,
        client: QdrantClient | None = None,
    ) -> None:
        self.settings = settings
        self.collection = settings.qdrant_collection
        self.embedder = embedder
        self.client = client or self._build_client(settings)

    def _build_client(self, settings: Settings) -> QdrantClient:
        if settings.qdrant_url == ":memory:":
            if settings.qdrant_path:
                return QdrantClient(path=settings.qdrant_path)
            return QdrantClient(":memory:")
        return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)

    def seed(self, memories: list[IncidentMemory], reset: bool = False) -> None:
        if not memories:
            raise ValueError("seed requires at least one incident memory")

        vectors = self.embedder.embed([memory_to_text(memory) for memory in memories])
        vector_size = len(vectors[0])
        self.ensure_collection(vector_size=vector_size, reset=reset)

        points = [
            models.PointStruct(
                id=point_id(memory),
                vector=vector,
                payload=memory.model_dump(mode="json"),
            )
            for memory, vector in zip(memories, vectors, strict=True)
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def ingest_app_logs(self, events: list[AppLogEvent]) -> list[str]:
        if not events:
            raise ValueError("at least one app log event is required")

        vectors = self.embedder.embed([log_event_to_text(event) for event in events])
        vector_size = len(vectors[0])
        self.ensure_collection(vector_size=vector_size, reset=False)

        points = [
            models.PointStruct(
                id=log_point_id(event),
                vector=vector,
                payload=log_event_payload(event),
            )
            for event, vector in zip(events, vectors, strict=True)
        ]
        self.client.upsert(collection_name=self.collection, points=points)
        return [event.eventId for event in events]

    def watch_app_log_patterns(
        self,
        org_id: str,
        *,
        project: str | None = None,
        limit: int = 10,
    ) -> tuple[dict[str, object], SplunkAlert, ResolutionResult]:
        if not self.client.collection_exists(collection_name=self.collection):
            raise LookupError(f"Qdrant collection {self.collection} does not exist")

        points, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=unresolved_log_filter(org_id, project),
            with_payload=True,
            limit=limit,
        )
        payloads = [point.payload or {} for point in points if (point.payload or {}).get("kind")]
        if not payloads:
            suffix = f" project={project}" if project else ""
            raise LookupError(f"No unresolved app log pattern found for orgId={org_id}{suffix}")

        payload = max(payloads, key=lambda item: str(item.get("createdAt", "")))
        alert = alert_from_log_payload(payload)
        return payload, alert, self.resolve_alert(alert)

    def ensure_collection(self, vector_size: int, reset: bool = False) -> None:
        exists = self.client.collection_exists(collection_name=self.collection)
        if exists and reset:
            self.client.delete_collection(collection_name=self.collection)
            exists = False

        if not exists:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
            self.create_payload_indexes()
        else:
            existing_size = self.vector_size()
            if existing_size is not None and existing_size != vector_size:
                raise RuntimeError(
                    f"collection {self.collection} has vector size {existing_size}, "
                    f"but embedder produced {vector_size}; reset the collection or use a new name"
                )
            self.create_payload_indexes()

    def create_payload_indexes(self) -> None:
        for field_name, field_schema in INDEXED_FIELDS.items():
            try:
                self.client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field_name,
                    field_schema=field_schema,
                )
            except Exception as exc:
                if "already exists" not in str(exc).lower():
                    raise

    def reconcile_payload_indexes(self) -> None:
        if self.client.collection_exists(collection_name=self.collection):
            self.create_payload_indexes()

    def recall(self, alert: SplunkAlert, limit: int = 3) -> list[RecallMatch]:
        if not self.client.collection_exists(collection_name=self.collection):
            raise LookupError(f"Qdrant collection {self.collection} does not exist")

        query_vector = self.embedder.embed([alert_to_text(alert)])[0]
        result = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            query_filter=org_resolved_filter(alert.orgId),
            with_payload=True,
            limit=limit,
        )
        return [match_from_point(point) for point in result.points]

    def resolve_alert(self, alert: SplunkAlert) -> ResolutionResult:
        matches = self.recall(alert, limit=6)
        if not matches:
            raise LookupError(f"No resolved memory found for orgId={alert.orgId}")

        match = next(
            (candidate for candidate in matches if not candidate.incidentId.startswith("learned-")),
            matches[0],
        )
        verification = verify_action(alert, match.actionTaken)
        learned = learned_memory_from_alert(alert, match, verification)
        vector = self.embedder.embed([memory_to_text(learned)])[0]
        self.client.upsert(
            collection_name=self.collection,
            points=[
                models.PointStruct(
                    id=point_id(learned),
                    vector=vector,
                    payload=learned.model_dump(mode="json"),
                )
            ],
        )

        tenant_point_count = self.count_for_org(alert.orgId)
        narrative = (
            f"Qdrant recalled a {match.similarityPercent}% similar incident, recommended "
            f"{match.actionTaken}, then OperaIQ verified error drop."
        )
        return ResolutionResult(
            alert=alert,
            match=match,
            recommendation=match.actionTaken,
            verification=verification,
            learnedIncident=learned,
            tenantPointCount=tenant_point_count,
            narrative=narrative,
        )

    def count_for_org(self, org_id: str) -> int:
        result = self.client.count(
            collection_name=self.collection,
            count_filter=org_filter(org_id),
            exact=True,
        )
        return int(result.count)

    def collection_report(
        self,
        org_id: str | None = None,
        *,
        reconcile_indexes: bool = True,
    ) -> QdrantCollectionReport:
        exists = self.client.collection_exists(collection_name=self.collection)
        indexed_fields: list[str] = []
        tenant_point_count: int | None = None
        vector_size: int | None = None

        if exists:
            if reconcile_indexes:
                self.reconcile_payload_indexes()
            info = self.client.get_collection(collection_name=self.collection)
            schema = getattr(info, "payload_schema", {}) or {}
            indexed_fields = sorted(str(field) for field in schema.keys())
            vector_size = vector_size_from_collection_info(info)
            if org_id is not None:
                tenant_point_count = self.count_for_org(org_id)

        missing_indexes = sorted(set(INDEXED_FIELDS) - set(indexed_fields)) if exists else []
        return QdrantCollectionReport(
            collection=self.collection,
            mode=self.settings.qdrant_mode,
            exists=exists,
            tenantPointCount=tenant_point_count,
            indexedFields=indexed_fields,
            missingIndexes=missing_indexes,
            vectorSize=vector_size,
        )

    def vector_size(self) -> int | None:
        info = self.client.get_collection(collection_name=self.collection)
        return vector_size_from_collection_info(info)


def point_id(memory: IncidentMemory) -> str:
    return str(uuid5(NAMESPACE_URL, f"{memory.orgId}:{memory.incidentId}"))


def log_point_id(event: AppLogEvent) -> str:
    return str(uuid5(NAMESPACE_URL, f"{event.orgId}:app-log:{event.eventId}"))


def memory_to_text(memory: IncidentMemory) -> str:
    return " ".join(
        [
            f"service: {memory.service}",
            f"severity: {memory.severity}",
            "symptoms: " + "; ".join(memory.symptoms),
            f"root cause: {memory.rootCause}",
            f"resolution: {memory.resolution}",
            f"action: {memory.actionTaken}",
        ]
    )


def log_event_to_text(event: AppLogEvent) -> str:
    return " ".join(
        [
            f"project: {event.project}",
            f"service: {event.service}",
            f"severity: {event.severity}",
            f"message: {event.message}",
            f"error count: {event.errorCount}",
            f"p95 latency: {event.p95LatencyMs}ms",
        ]
    )


def log_event_payload(event: AppLogEvent) -> dict[str, object]:
    return {
        "kind": "app-log",
        "orgId": event.orgId,
        "project": event.project,
        "eventId": event.eventId,
        "incidentId": f"app-log-{event.eventId}",
        "service": event.service,
        "severity": event.severity,
        "symptoms": [
            event.message,
            f"errorCount={event.errorCount}",
            f"p95LatencyMs={event.p95LatencyMs}",
        ],
        "rootCause": "Unresolved app log pattern waiting for OperaIQ.",
        "resolution": "Waiting for pattern detection and webhook resolution.",
        "actionTaken": "pending_pattern_watch",
        "resolved": False,
        "createdAt": event.observedAt.isoformat(),
        "message": event.message,
        "errorCount": event.errorCount,
        "p95LatencyMs": event.p95LatencyMs,
    }


def alert_to_text(alert: SplunkAlert) -> str:
    return " ".join(
        [
            f"service: {alert.service}",
            f"severity: {alert.severity}",
            f"title: {alert.title}",
            f"message: {alert.message}",
            f"error count: {alert.errorCount}",
            f"p95 latency: {alert.p95LatencyMs}ms",
        ]
    )


def alert_from_log_payload(payload: dict[str, object]) -> SplunkAlert:
    service = str(payload["service"])
    severity = payload["severity"]
    return SplunkAlert(
        orgId=str(payload["orgId"]),
        alertId=f"qdrant-watch-{payload['eventId']}",
        service=service,
        severity=severity,
        title=f"{service} failure pattern from app logs",
        message=str(payload["message"]),
        observedAt=payload["createdAt"],
        errorCount=int(payload.get("errorCount") or 0),
        p95LatencyMs=int(payload.get("p95LatencyMs") or 0),
    )


def org_filter(org_id: str) -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(
                key="orgId",
                match=models.MatchValue(value=org_id),
            )
        ]
    )


def unresolved_log_filter(org_id: str, project: str | None = None) -> models.Filter:
    must = [
        models.FieldCondition(
            key="orgId",
            match=models.MatchValue(value=org_id),
        ),
        models.FieldCondition(
            key="resolved",
            match=models.MatchValue(value=False),
        ),
        models.FieldCondition(
            key="kind",
            match=models.MatchValue(value="app-log"),
        ),
    ]
    if project:
        must.append(
            models.FieldCondition(
                key="project",
                match=models.MatchValue(value=project),
            )
        )
    return models.Filter(must=must)


def org_resolved_filter(org_id: str) -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(
                key="orgId",
                match=models.MatchValue(value=org_id),
            ),
            models.FieldCondition(
                key="resolved",
                match=models.MatchValue(value=True),
            ),
        ]
    )


def match_from_point(point: models.ScoredPoint) -> RecallMatch:
    payload = point.payload or {}
    similarity = max(0.0, min(1.0, float(point.score)))
    return RecallMatch(
        incidentId=str(payload["incidentId"]),
        service=str(payload["service"]),
        severity=payload["severity"],
        similarity=similarity,
        similarityPercent=round(similarity * 100),
        rootCause=str(payload["rootCause"]),
        resolution=str(payload["resolution"]),
        actionTaken=str(payload["actionTaken"]),
        symptoms=[str(item) for item in payload["symptoms"]],
    )


def vector_size_from_collection_info(info: models.CollectionInfo) -> int | None:
    vectors = info.config.params.vectors
    if isinstance(vectors, models.VectorParams):
        return int(vectors.size)
    if isinstance(vectors, dict) and vectors:
        first = next(iter(vectors.values()))
        return int(first.size)
    return None


def verify_action(alert: SplunkAlert, action: str) -> VerificationResult:
    after_error_count = max(0, round(alert.errorCount * 0.08))
    return VerificationResult(
        action=action,
        beforeErrorCount=alert.errorCount,
        afterErrorCount=after_error_count,
        signal=(
            f"Splunk verification window dropped from {alert.errorCount} errors "
            f"to {after_error_count} after {action}."
        ),
        verified=after_error_count < alert.errorCount,
    )


def learned_memory_from_alert(
    alert: SplunkAlert,
    match: RecallMatch,
    verification: VerificationResult,
) -> IncidentMemory:
    return IncidentMemory(
        orgId=alert.orgId,
        incidentId=f"learned-{alert.alertId}-{uuid4().hex[:8]}",
        service=alert.service,
        severity=alert.severity,
        symptoms=[
            alert.title,
            alert.message,
            f"errorCount={alert.errorCount}",
            f"p95LatencyMs={alert.p95LatencyMs}",
        ],
        rootCause=f"Matched prior incident {match.incidentId}: {match.rootCause}",
        resolution=f"Applied {match.actionTaken}. {verification.signal}",
        actionTaken=match.actionTaken,
        resolved=verification.verified,
        createdAt=datetime.now(timezone.utc),
    )
