from app.config import get_settings
from app.embedder import FastEmbedEmbedder
from app.memory_service import IncidentMemoryService
from app.seed import DEFAULT_ALERT, SEED_INCIDENTS


def main() -> None:
    settings = get_settings()
    service = IncidentMemoryService(
        settings=settings,
        embedder=FastEmbedEmbedder(settings.embedding_model),
    )
    service.seed(SEED_INCIDENTS, reset=True)
    result = service.resolve_alert(DEFAULT_ALERT)

    print(result.narrative)
    print(f"recalled_incident={result.match.incidentId}")
    print(f"similarity={result.match.similarityPercent}%")
    print(f"recommended_action={result.recommendation}")
    print(f"verification={result.verification.signal}")
    print(f"learned_incident={result.learnedIncident.incidentId}")
    print(f"tenant_point_count={result.tenantPointCount}")


if __name__ == "__main__":
    main()
