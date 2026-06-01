from functools import lru_cache
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.embedder import FastEmbedEmbedder
from app.memory_service import IncidentMemoryService
from app.models import (
    AppLogEvent,
    HealthResponse,
    LogIngestRequest,
    LogIngestResponse,
    PatternWatchRequest,
    PatternWatchResult,
    ReadinessResponse,
    ResolutionResult,
    SplunkAlert,
    WebhookIncidentEvent,
    WebhookIntegrationRequest,
    WebhookIntegrationResponse,
)
from app.seed import DEFAULT_ALERT, SEED_INCIDENTS
from app.webhooks import (
    verify_webhook_signature,
    webhook_path,
    webhook_secret,
    webhook_url,
)


app = FastAPI(title="OperaIQ", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@lru_cache
def get_memory_service() -> IncidentMemoryService:
    settings = get_settings()
    return IncidentMemoryService(
        settings=settings,
        embedder=FastEmbedEmbedder(settings.embedding_model),
    )


def require_write_access(authorization: str | None) -> None:
    settings = get_settings()
    if settings.allow_unauthenticated_writes:
        return
    if not settings.operaiq_api_token:
        raise HTTPException(status_code=503, detail="write token is not configured")
    if authorization != f"Bearer {settings.operaiq_api_token}":
        raise HTTPException(status_code=401, detail="valid OperaIQ write token required")


def resolve_app_event(
    service: IncidentMemoryService,
    event: AppLogEvent,
    *,
    inbound_webhook_path: str,
) -> PatternWatchResult:
    try:
        service.ingest_app_logs([event])
        payload, alert, resolution = service.watch_app_log_patterns(
            event.orgId,
            project=event.project,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return PatternWatchResult(
        sourceEventId=str(payload["eventId"]),
        sourceProject=str(payload["project"]),
        pattern=f"{alert.service} {alert.severity} app-log pattern",
        webhookPath=inbound_webhook_path,
        webhookAccepted=True,
        alert=alert,
        resolution=resolution,
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "app_name": get_settings().app_name,
            "collection": get_settings().qdrant_collection,
            "qdrant_mode": get_settings().qdrant_mode,
            "default_alert": DEFAULT_ALERT.model_dump(mode="json"),
        },
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    report = get_memory_service().collection_report(org_id=DEFAULT_ALERT.orgId)
    indexed_enough = report.mode != "server" or not report.missingIndexes
    return HealthResponse(
        status="ok" if report.exists and indexed_enough else "degraded",
        app=settings.app_name,
        env=settings.app_env,
        qdrant=report,
    )


@app.get("/runtime/readiness", response_model=ReadinessResponse)
def readiness() -> ReadinessResponse:
    settings = get_settings()
    report = get_memory_service().collection_report(org_id=DEFAULT_ALERT.orgId)
    issues = settings.production_issues()
    warnings = settings.production_warnings()

    if not report.exists:
        issues.append(f"Qdrant collection {report.collection} has not been created")
    if report.missingIndexes and report.mode == "server":
        issues.append("missing payload indexes: " + ", ".join(report.missingIndexes))
    if report.missingIndexes and report.mode != "server":
        warnings.append("local Qdrant mode does not expose active payload index proof")
    if report.mode == "local-path":
        warnings.append("local Qdrant path is persistent but not a multi-process production server")

    return ReadinessResponse(
        ready=len(issues) == 0,
        production=settings.is_production,
        issues=issues,
        warnings=warnings,
        qdrant=report,
    )


@app.post("/api/seed")
def seed(
    reset: bool = False,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    require_write_access(authorization)
    if reset and not get_settings().allow_collection_reset:
        raise HTTPException(status_code=403, detail="collection reset is disabled")

    service = get_memory_service()
    try:
        service.seed(SEED_INCIDENTS, reset=reset)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "collection": service.collection,
        "seeded": len(SEED_INCIDENTS),
        "tenantPointCount": service.count_for_org(DEFAULT_ALERT.orgId),
    }


@app.post("/api/app/logs", response_model=LogIngestResponse)
def ingest_app_logs(
    request: LogIngestRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> LogIngestResponse:
    require_write_access(authorization)
    service = get_memory_service()
    try:
        event_ids = service.ingest_app_logs(request.events)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    first_event = request.events[0]
    return LogIngestResponse(
        stored=len(event_ids),
        orgId=first_event.orgId,
        project=first_event.project,
        eventIds=event_ids,
        tenantPointCount=service.count_for_org(first_event.orgId),
    )


@app.post("/api/integrations/webhook", response_model=WebhookIntegrationResponse)
def create_webhook_integration(
    integration: WebhookIntegrationRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> WebhookIntegrationResponse:
    require_write_access(authorization)
    settings = get_settings()
    path = webhook_path(
        integration.orgId,
        integration.project,
        webhook_secret(settings),
    )
    return WebhookIntegrationResponse(
        orgId=integration.orgId,
        project=integration.project,
        webhookUrl=webhook_url(request, settings, path),
        webhookPath=path,
        authMode="signed-url",
        deliveryMethod="POST",
        expectedPayload={
            "eventId": "source-event-id",
            "service": DEFAULT_ALERT.service,
            "severity": DEFAULT_ALERT.severity,
            "message": DEFAULT_ALERT.message,
            "errorCount": DEFAULT_ALERT.errorCount,
            "p95LatencyMs": DEFAULT_ALERT.p95LatencyMs,
        },
    )


@app.post("/api/qdrant/watch", response_model=PatternWatchResult)
def watch_qdrant_patterns(
    request: PatternWatchRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> PatternWatchResult:
    require_write_access(authorization)
    service = get_memory_service()
    try:
        payload, alert, resolution = service.watch_app_log_patterns(
            request.orgId,
            project=request.project,
            limit=request.limit,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    source_project = str(payload["project"])
    settings = get_settings()
    path = webhook_path(
        alert.orgId,
        source_project,
        webhook_secret(settings),
    )
    return PatternWatchResult(
        sourceEventId=str(payload["eventId"]),
        sourceProject=source_project,
        pattern=f"{alert.service} {alert.severity} app-log pattern",
        webhookPath=path,
        webhookAccepted=True,
        alert=alert,
        resolution=resolution,
    )


@app.post("/api/webhooks/{org_id}/{project}/{signature}", response_model=PatternWatchResult)
def signed_source_webhook(
    org_id: str,
    project: str,
    signature: str,
    event: WebhookIncidentEvent,
) -> PatternWatchResult:
    settings = get_settings()
    secret = webhook_secret(settings)
    if not verify_webhook_signature(secret, org_id, project, signature):
        raise HTTPException(status_code=401, detail="invalid webhook signature")

    service = get_memory_service()
    app_event = AppLogEvent(
        orgId=org_id,
        project=project,
        eventId=event.eventId,
        service=event.service,
        severity=event.severity,
        message=event.message,
        observedAt=event.observedAt,
        errorCount=event.errorCount,
        p95LatencyMs=event.p95LatencyMs,
    )
    return resolve_app_event(
        service,
        app_event,
        inbound_webhook_path=webhook_path(org_id, project, secret),
    )


@app.post("/api/alerts/resolve", response_model=ResolutionResult)
def resolve_alert(
    alert: SplunkAlert,
    authorization: Annotated[str | None, Header()] = None,
) -> ResolutionResult:
    require_write_access(authorization)
    service = get_memory_service()
    try:
        return service.resolve_alert(alert)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
