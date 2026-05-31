from app.config import Settings
from app.embedder import KeywordEmbedder
from app.memory_service import IncidentMemoryService
from app.seed import DEFAULT_ALERT, SEED_INCIDENTS


def test_qdrant_recalls_with_org_filter_and_writes_back() -> None:
    service = IncidentMemoryService(
        settings=Settings(qdrant_url=":memory:"),
        embedder=KeywordEmbedder(),
    )
    service.seed(SEED_INCIDENTS, reset=True)

    before_count = service.count_for_org(DEFAULT_ALERT.orgId)
    result = service.resolve_alert(DEFAULT_ALERT)

    assert result.match.incidentId == "inc-redis-econnreset-2026-05-21"
    assert result.recommendation == "rotate_connection_pool"
    assert result.verification.verified is True
    assert result.tenantPointCount == before_count + 1
    assert result.learnedIncident.orgId == DEFAULT_ALERT.orgId
    assert result.learnedIncident.actionTaken == "rotate_connection_pool"


def test_org_filter_blocks_cross_tenant_redis_memory() -> None:
    service = IncidentMemoryService(
        settings=Settings(qdrant_url=":memory:"),
        embedder=KeywordEmbedder(),
    )
    service.seed(SEED_INCIDENTS, reset=True)

    globex_alert = DEFAULT_ALERT.model_copy(
        update={
            "orgId": "globex-payments",
            "alertId": "splunk-alert-globex-redis",
            "service": "settlement-api",
        }
    )
    result = service.resolve_alert(globex_alert)

    assert result.match.incidentId == "inc-redis-econnreset-globex-2026-05-23"
    assert result.learnedIncident.orgId == "globex-payments"

