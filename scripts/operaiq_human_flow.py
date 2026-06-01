from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.models import AppLogEvent, PatternWatchRequest
from app.seed import DEFAULT_ALERT


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the OperaIQ human proof flow.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8097")
    parser.add_argument("--artifact-dir", default=None)
    parser.add_argument("--api-token", default=os.getenv("OPERAIQ_API_TOKEN"))
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--project", default=None)
    args = parser.parse_args()

    settings = get_settings()
    artifact_dir = Path(args.artifact_dir or settings.proof_artifacts_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc)
    project = args.project or f"fresh-project-{generated_at.strftime('%Y%m%d%H%M%S')}"
    checks: list[dict[str, object]] = []
    headers = {"Authorization": f"Bearer {args.api_token}"} if args.api_token else {}

    def record(name: str, passed: bool, evidence: object) -> None:
        checks.append({"name": name, "passed": passed, "evidence": evidence})
        if not passed:
            raise AssertionError(f"{name} failed: {evidence}")

    with httpx.Client(base_url=args.base_url, timeout=60.0) as client:
        ui = client.get("/")
        record(
            "ui_loads_operaiq_console",
            ui.status_code == 200 and "watcher finds a pattern" in ui.text,
            {"status": ui.status_code, "containsWatcherCopy": "watcher finds a pattern" in ui.text},
        )

        seed = client.post("/api/seed", params={"reset": str(args.reset).lower()}, headers=headers)
        seed_json = seed.json()
        record(
            "seeded_realistic_memories",
            seed.status_code == 200 and seed_json.get("tenantPointCount", 0) >= 8,
            seed_json,
        )
        acme_count_before = int(seed_json["tenantPointCount"])

        health = client.get("/health")
        health_json = health.json()
        record(
            "health_ok_after_seed",
            health.status_code == 200 and health_json.get("status") == "ok",
            health_json,
        )

        readiness = client.get("/runtime/readiness")
        readiness_json = readiness.json()
        record(
            "runtime_ready_after_seed",
            readiness.status_code == 200 and readiness_json.get("ready") is True,
            readiness_json,
        )

        app_log = AppLogEvent(
            orgId=DEFAULT_ALERT.orgId,
            project=project,
            eventId=f"app-log-{generated_at.strftime('%Y%m%d%H%M%S')}",
            service=DEFAULT_ALERT.service,
            severity=DEFAULT_ALERT.severity,
            message=DEFAULT_ALERT.message,
            observedAt=generated_at,
            errorCount=DEFAULT_ALERT.errorCount,
            p95LatencyMs=DEFAULT_ALERT.p95LatencyMs,
        )
        log = client.post(
            "/api/app/logs",
            json={"events": [app_log.model_dump(mode="json")]},
            headers=headers,
        )
        log_json = log.json()
        record(
            "app_logs_written_to_qdrant",
            log.status_code == 200
            and log_json.get("stored") == 1
            and log_json.get("tenantPointCount") == acme_count_before + 1,
            log_json,
        )

        watch_request = PatternWatchRequest(orgId=DEFAULT_ALERT.orgId, project=project)
        watch = client.post(
            "/api/qdrant/watch",
            json=watch_request.model_dump(mode="json"),
            headers=headers,
        )
        watch_json = watch.json()
        acme_json = watch_json.get("resolution", {})
        record(
            "qdrant_watch_fired_webhook_and_operaiq_learned",
            watch.status_code == 200
            and watch_json.get("webhookFired") is True
            and watch_json.get("webhookPath") == "/api/webhooks/pattern-alert"
            and acme_json["match"]["incidentId"] == "inc-redis-econnreset-2026-05-21"
            and acme_json["recommendation"] == "rotate_connection_pool"
            and acme_json["verification"]["verified"] is True
            and acme_json["tenantPointCount"] == acme_count_before + 2,
            watch_json,
        )

        globex_alert = DEFAULT_ALERT.model_copy(
            update={
                "orgId": "globex-payments",
                "alertId": f"human-globex-{generated_at.strftime('%Y%m%d%H%M%S')}",
                "service": "settlement-api",
            }
        )
        globex = client.post(
            "/api/alerts/resolve",
            json=globex_alert.model_dump(mode="json"),
            headers=headers,
        )
        globex_json = globex.json()
        record(
            "tenant_filter_blocks_cross_org_memory",
            globex.status_code == 200
            and globex_json["match"]["incidentId"] == "inc-redis-econnreset-globex-2026-05-23"
            and globex_json["learnedIncident"]["orgId"] == "globex-payments",
            globex_json,
        )

        final_health = client.get("/health").json()

    artifact = {
        "app": "OperaIQ",
        "baseUrl": args.base_url,
        "project": project,
        "generatedAt": generated_at.isoformat(),
        "accepted": all(check["passed"] for check in checks),
        "checks": checks,
        "finalHealth": final_health,
        "proofSummary": {
            "flow": "app logs -> Qdrant unresolved signal -> watcher webhook -> OperaIQ resolve -> Qdrant learned memory",
            "loggedEvent": log_json["eventIds"][0],
            "webhookPath": watch_json["webhookPath"],
            "acmeMatch": acme_json["match"]["incidentId"],
            "acmeAction": acme_json["recommendation"],
            "acmeSimilarityPercent": acme_json["match"]["similarityPercent"],
            "acmeTenantPointCount": acme_json["tenantPointCount"],
            "globexMatch": globex_json["match"]["incidentId"],
            "globexTenantPointCount": globex_json["tenantPointCount"],
        },
    }

    artifact_path = artifact_dir / f"operaiq-human-flow-{generated_at.strftime('%Y%m%d%H%M%S')}.json"
    artifact_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    print(f"accepted={artifact['accepted']}")
    print(f"artifact={artifact_path}")
    print(f"project={project}")
    print(f"flow={artifact['proofSummary']['flow']}")
    print(f"webhook_path={artifact['proofSummary']['webhookPath']}")
    print(f"acme_match={artifact['proofSummary']['acmeMatch']}")
    print(f"acme_action={artifact['proofSummary']['acmeAction']}")
    print(f"acme_similarity={artifact['proofSummary']['acmeSimilarityPercent']}%")
    print(f"globex_match={artifact['proofSummary']['globexMatch']}")


if __name__ == "__main__":
    main()
