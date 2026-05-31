from fastapi.testclient import TestClient

from app.config import Settings
from app.embedder import KeywordEmbedder
import app.main as main
from app.memory_service import IncidentMemoryService
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
            allow_judge_quick_run=False,
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


def test_judge_quick_run_can_be_enabled_without_general_writes(monkeypatch) -> None:
    service = IncidentMemoryService(
        settings=Settings(
            app_env="production",
            qdrant_url=":memory:",
            allow_unauthenticated_writes=False,
            allow_judge_quick_run=True,
        ),
        embedder=KeywordEmbedder(),
    )

    monkeypatch.setattr(main, "get_settings", lambda: service.settings)
    monkeypatch.setattr(main, "get_memory_service", lambda: service)
    client = TestClient(main.app)

    response = client.post("/api/judge/quick-run?reset=false")
    assert response.status_code == 200
    assert response.json()["recommendation"] == "rotate_connection_pool"
