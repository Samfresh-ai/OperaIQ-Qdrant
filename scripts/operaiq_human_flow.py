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
from app.models import WebhookIncidentEvent, WebhookIntegrationRequest
from app.seed import DEFAULT_ALERT


def masked_path(path: str) -> str:
    parts = path.rstrip("/").split("/")
    if len(parts) < 2:
        return path
    parts[-1] = f"{parts[-1][:6]}...{parts[-1][-4:]}"
    return "/".join(parts)


def sanitize(value):
    if isinstance(value, dict):
        return {
            key: masked_path(item) if key in {"webhookPath", "webhookUrl"} and isinstance(item, str) else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


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
        checks.append({"name": name, "passed": passed, "evidence": sanitize(evidence)})
        if not passed:
            raise AssertionError(f"{name} failed: {sanitize(evidence)}")

    with httpx.Client(base_url=args.base_url, timeout=60.0) as client:
        ui = client.get("/")
        record(
            "ui_loads_operaiq_console",
            ui.status_code == 200 and "Generate a signed URL" in ui.text,
            {"status": ui.status_code, "containsWebhookUrl": "Generate a signed URL" in ui.text},
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

        integration_request = WebhookIntegrationRequest(orgId=DEFAULT_ALERT.orgId, project=project)
        integration = client.post(
            "/api/integrations/webhook",
            json=integration_request.model_dump(mode="json"),
            headers=headers,
        )
        integration_json = integration.json()
        record(
            "signed_webhook_url_generated",
            integration.status_code == 200
            and integration_json.get("authMode") == "signed-url"
            and str(integration_json.get("webhookPath", "")).startswith(
                f"/api/webhooks/{DEFAULT_ALERT.orgId}/{project}/"
            ),
            integration_json,
        )

        source_event = WebhookIncidentEvent(
            eventId=f"app-log-{generated_at.strftime('%Y%m%d%H%M%S')}",
            service=DEFAULT_ALERT.service,
            severity=DEFAULT_ALERT.severity,
            message=DEFAULT_ALERT.message,
            observedAt=generated_at,
            errorCount=DEFAULT_ALERT.errorCount,
            p95LatencyMs=DEFAULT_ALERT.p95LatencyMs,
        )
        source_delivery = client.post(
            integration_json["webhookPath"],
            json=source_event.model_dump(mode="json"),
        )
        source_delivery_json = source_delivery.json()
        acme_json = source_delivery_json.get("resolution", {})
        record(
            "source_webhook_accepted_and_operaiq_learned",
            source_delivery.status_code == 200
            and source_delivery_json.get("webhookAccepted") is True
            and source_delivery_json.get("webhookPath") == integration_json["webhookPath"]
            and acme_json["match"]["incidentId"] == "inc-redis-econnreset-2026-05-21"
            and acme_json["recommendation"] == "rotate_connection_pool"
            and acme_json["verification"]["verified"] is True
            and acme_json["tenantPointCount"] == acme_count_before + 2,
            source_delivery_json,
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
            "flow": "source webhook -> Qdrant unresolved signal -> OperaIQ autonomous response -> Qdrant learned memory",
            "loggedEvent": source_delivery_json["sourceEventId"],
            "webhookPath": masked_path(source_delivery_json["webhookPath"]),
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
