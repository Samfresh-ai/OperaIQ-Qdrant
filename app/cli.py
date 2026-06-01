import argparse

from app.config import get_settings
from app.embedder import FastEmbedEmbedder
from app.memory_service import IncidentMemoryService
from app.models import AppLogEvent
from app.seed import DEFAULT_ALERT, SEED_INCIDENTS
from app.webhooks import webhook_path, webhook_secret


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the OperaIQ local incident-learning flow.")
    parser.add_argument("--reset", action="store_true", help="Reset the local collection before seeding.")
    parser.add_argument("--project", default="cli-local-project")
    args = parser.parse_args()

    settings = get_settings()
    service = IncidentMemoryService(
        settings=settings,
        embedder=FastEmbedEmbedder(settings.embedding_model),
    )
    service.seed(SEED_INCIDENTS, reset=args.reset)
    event = AppLogEvent(
        orgId=DEFAULT_ALERT.orgId,
        project=args.project,
        service=DEFAULT_ALERT.service,
        severity=DEFAULT_ALERT.severity,
        message=DEFAULT_ALERT.message,
        errorCount=DEFAULT_ALERT.errorCount,
        p95LatencyMs=DEFAULT_ALERT.p95LatencyMs,
    )
    event_ids = service.ingest_app_logs([event])
    payload, alert, result = service.watch_app_log_patterns(
        DEFAULT_ALERT.orgId,
        project=args.project,
    )

    inbound_path = webhook_path(DEFAULT_ALERT.orgId, args.project, webhook_secret(settings))

    print("Your app -> signed OperaIQ webhook -> Qdrant memory -> autonomous response -> learned memory")
    print(f"app={settings.app_name}")
    print(f"qdrant_mode={settings.qdrant_mode}")
    print(f"project={args.project}")
    print(f"logged_event={event_ids[0]}")
    print(f"watcher_pattern={payload['service']} {payload['severity']}")
    print(f"webhook_path={inbound_path}")
    print(f"webhook_alert={alert.alertId}")
    print(f"recalled_incident={result.match.incidentId}")
    print(f"similarity={result.match.similarityPercent}%")
    print(f"recommended_action={result.recommendation}")
    print(f"verification={result.verification.signal}")
    print(f"learned_incident={result.learnedIncident.incidentId}")
    print(f"tenant_point_count={result.tenantPointCount}")


if __name__ == "__main__":
    main()
