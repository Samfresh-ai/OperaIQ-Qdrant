from fastapi.testclient import TestClient

from app.config import Settings
from app.embedder import KeywordEmbedder
import app.main as main
from app.memory_service import IncidentMemoryService
from app.models import AppLogEvent
from app.seed import DEFAULT_ALERT


def test_api_health_readiness_resolve_and_tenant_isolation(monkeypatch) -> None:
    service = IncidentMemoryService(
        settings=Settings(qdrant_url=":memory:"),
        embedder=KeywordEmbedder(),
    )

    monkeypatch.setattr(main, "get_memory_service", lambda: service)
    client = TestClient(main.app)

    seed_response = client.post("/api/seed?reset=false")
    assert seed_response.status_code == 200
    assert seed_response.json()["tenantPointCount"] == 8

    health_response = client.get("/health")
    assert health_response.status_code == 200
    health = health_response.json()
    assert health["status"] == "ok"
    assert set(health["qdrant"]["missingIndexes"]) == {
        "orgId",
        "service",
        "severity",
        "resolved",
        "createdAt",
        "kind",
        "project",
    }

    readiness_response = client.get("/runtime/readiness")
    assert readiness_response.status_code == 200
    readiness = readiness_response.json()
    assert readiness["ready"] is True
    assert readiness["issues"] == []
    assert readiness["warnings"] == ["local Qdrant mode does not expose active payload index proof"]

    resolve_response = client.post(
        "/api/alerts/resolve",
        json=DEFAULT_ALERT.model_dump(mode="json"),
    )
    assert resolve_response.status_code == 200
    result = resolve_response.json()
    assert result["match"]["incidentId"] == "inc-redis-econnreset-2026-05-21"
    assert result["recommendation"] == "rotate_connection_pool"
    assert result["verification"]["verified"] is True
    assert result["tenantPointCount"] == 9

    globex_alert = DEFAULT_ALERT.model_copy(
        update={
            "orgId": "globex-payments",
            "alertId": "splunk-alert-globex-redis",
            "service": "settlement-api",
        }
    )
    globex_response = client.post(
        "/api/alerts/resolve",
        json=globex_alert.model_dump(mode="json"),
    )
    assert globex_response.status_code == 200
    globex = globex_response.json()
    assert globex["match"]["incidentId"] == "inc-redis-econnreset-globex-2026-05-23"
    assert globex["learnedIncident"]["orgId"] == "globex-payments"


def test_app_log_watch_flow_fires_webhook_and_writes_learned_memory(monkeypatch) -> None:
    service = IncidentMemoryService(
        settings=Settings(qdrant_url=":memory:"),
        embedder=KeywordEmbedder(),
    )

    monkeypatch.setattr(main, "get_memory_service", lambda: service)
    client = TestClient(main.app)

    seed_response = client.post("/api/seed?reset=false")
    assert seed_response.status_code == 200
    assert seed_response.json()["tenantPointCount"] == 8

    event = AppLogEvent(
        orgId=DEFAULT_ALERT.orgId,
        project="new-checkout-project",
        eventId="unit-log-redis",
        service=DEFAULT_ALERT.service,
        severity=DEFAULT_ALERT.severity,
        message=DEFAULT_ALERT.message,
        errorCount=DEFAULT_ALERT.errorCount,
        p95LatencyMs=DEFAULT_ALERT.p95LatencyMs,
    )
    ingest = client.post("/api/app/logs", json={"events": [event.model_dump(mode="json")]})
    assert ingest.status_code == 200
    assert ingest.json()["tenantPointCount"] == 9

    watch = client.post(
        "/api/qdrant/watch",
        json={"orgId": DEFAULT_ALERT.orgId, "project": "new-checkout-project"},
    )
    assert watch.status_code == 200
    result = watch.json()
    assert result["webhookFired"] is True
    assert result["webhookPath"] == "/api/webhooks/pattern-alert"
    assert result["resolution"]["match"]["incidentId"] == "inc-redis-econnreset-2026-05-21"
    assert result["resolution"]["recommendation"] == "rotate_connection_pool"
    assert result["resolution"]["tenantPointCount"] == 10


def test_seed_without_reset_preserves_custom_org_data(monkeypatch) -> None:
    service = IncidentMemoryService(
        settings=Settings(qdrant_url=":memory:"),
        embedder=KeywordEmbedder(),
    )

    monkeypatch.setattr(main, "get_memory_service", lambda: service)
    client = TestClient(main.app)

    assert client.post("/api/seed?reset=false").status_code == 200
    custom_event = AppLogEvent(
        orgId="custom-org",
        project="custom-project",
        service=DEFAULT_ALERT.service,
        severity=DEFAULT_ALERT.severity,
        message=DEFAULT_ALERT.message,
        errorCount=DEFAULT_ALERT.errorCount,
        p95LatencyMs=DEFAULT_ALERT.p95LatencyMs,
    )
    assert client.post(
        "/api/app/logs",
        json={"events": [custom_event.model_dump(mode="json")]},
    ).status_code == 200

    reseed = client.post("/api/seed?reset=false")

    assert reseed.status_code == 200
    assert service.count_for_org("custom-org") == 1


def test_resolve_without_seed_returns_clear_404(monkeypatch) -> None:
    service = IncidentMemoryService(
        settings=Settings(qdrant_url=":memory:"),
        embedder=KeywordEmbedder(),
    )

    monkeypatch.setattr(main, "get_memory_service", lambda: service)
    client = TestClient(main.app)

    response = client.post("/api/alerts/resolve", json=DEFAULT_ALERT.model_dump(mode="json"))

    assert response.status_code == 404
    assert "does not exist" in response.json()["detail"]


def test_production_write_paths_require_token(monkeypatch) -> None:
    service = IncidentMemoryService(
        settings=Settings(
            app_env="production",
            qdrant_url=":memory:",
            operaiq_api_token="secret-token",
            allow_unauthenticated_writes=False,
        ),
        embedder=KeywordEmbedder(),
    )

    monkeypatch.setattr(main, "get_settings", lambda: service.settings)
    monkeypatch.setattr(main, "get_memory_service", lambda: service)
    client = TestClient(main.app)

    blocked = client.post("/api/seed?reset=false")
    assert blocked.status_code == 401

    allowed = client.post(
        "/api/seed?reset=false",
        headers={"Authorization": "Bearer secret-token"},
    )
    assert allowed.status_code == 200


def test_collection_reset_stays_disabled_by_default(monkeypatch) -> None:
    service = IncidentMemoryService(
        settings=Settings(
            qdrant_url=":memory:",
        ),
        embedder=KeywordEmbedder(),
    )

    monkeypatch.setattr(main, "get_memory_service", lambda: service)
    client = TestClient(main.app)

    response = client.post("/api/seed?reset=true")
    assert response.status_code == 403
    assert response.json()["detail"] == "collection reset is disabled"
