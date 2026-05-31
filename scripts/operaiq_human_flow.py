from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.seed import DEFAULT_ALERT


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the OperaIQ human proof flow.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8097")
    parser.add_argument("--artifact-dir", default=None)
    args = parser.parse_args()

    settings = get_settings()
    artifact_dir = Path(args.artifact_dir or settings.proof_artifacts_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc)
    checks: list[dict[str, object]] = []

    def record(name: str, passed: bool, evidence: object) -> None:
        checks.append({"name": name, "passed": passed, "evidence": evidence})
        if not passed:
            raise AssertionError(f"{name} failed: {evidence}")

    with httpx.Client(base_url=args.base_url, timeout=60.0) as client:
        ui = client.get("/")
        record(
            "ui_loads_operaiq_console",
            ui.status_code == 200 and "OperaIQ remembers" in ui.text,
            {"status": ui.status_code, "containsOperaIQ": "OperaIQ remembers" in ui.text},
        )

        seed = client.post("/api/seed", params={"reset": "true"})
        seed_json = seed.json()
        record(
            "seeded_realistic_memories",
            seed.status_code == 200 and seed_json.get("tenantPointCount") == 8,
            seed_json,
        )

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

        acme_alert = DEFAULT_ALERT.model_copy(
            update={"alertId": f"human-acme-{generated_at.strftime('%Y%m%d%H%M%S')}"}
        )
        acme = client.post("/api/alerts/resolve", json=acme_alert.model_dump(mode="json"))
        acme_json = acme.json()
        record(
            "acme_alert_recalled_verified_and_learned",
            acme.status_code == 200
            and acme_json["match"]["incidentId"] == "inc-redis-econnreset-2026-05-21"
            and acme_json["recommendation"] == "rotate_connection_pool"
            and acme_json["verification"]["verified"] is True
            and acme_json["tenantPointCount"] == 9,
            acme_json,
        )

        globex_alert = DEFAULT_ALERT.model_copy(
            update={
                "orgId": "globex-payments",
                "alertId": f"human-globex-{generated_at.strftime('%Y%m%d%H%M%S')}",
                "service": "settlement-api",
            }
        )
        globex = client.post("/api/alerts/resolve", json=globex_alert.model_dump(mode="json"))
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
        "generatedAt": generated_at.isoformat(),
        "accepted": all(check["passed"] for check in checks),
        "checks": checks,
        "finalHealth": final_health,
        "proofSummary": {
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
    print(f"acme_match={artifact['proofSummary']['acmeMatch']}")
    print(f"acme_action={artifact['proofSummary']['acmeAction']}")
    print(f"acme_similarity={artifact['proofSummary']['acmeSimilarityPercent']}%")
    print(f"globex_match={artifact['proofSummary']['globexMatch']}")


if __name__ == "__main__":
    main()
