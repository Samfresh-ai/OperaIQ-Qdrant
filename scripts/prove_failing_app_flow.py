from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import httpx


def masked_path(path: str | None) -> str | None:
    if not path:
        return path
    parts = path.rstrip("/").split("/")
    if len(parts) < 2:
        return path
    parts[-1] = f"{parts[-1][:6]}...{parts[-1][-4:]}"
    return "/".join(parts)


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: masked_path(item) if key in {"webhookPath", "webhookUrl"} and isinstance(item, str) else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def wait_for_source_app(base_url: str) -> None:
    deadline = time.time() + 30
    last_error: str | None = None
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url}/health", timeout=2.0)
            if response.status_code == 200:
                return
            last_error = f"status {response.status_code}"
        except Exception as exc:  # noqa: BLE001 - proof script should preserve the last connection failure
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"failing checkout app did not become ready: {last_error}")


def record(checks: list[dict[str, object]], name: str, passed: bool, evidence: object) -> None:
    checks.append({"name": name, "passed": passed, "evidence": sanitize(evidence)})
    if not passed:
        raise AssertionError(f"{name} failed: {sanitize(evidence)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prove a real failing source app can drive OperaIQ through the public webhook flow."
    )
    parser.add_argument("--operaiq-base-url", default=os.getenv("OPERAIQ_BASE_URL", "http://127.0.0.1:8097"))
    parser.add_argument("--api-token", default=os.getenv("OPERAIQ_API_TOKEN"))
    parser.add_argument("--source-app-port", type=int, default=8891)
    parser.add_argument("--artifact-dir", default=os.getenv("PROOF_ARTIFACTS_DIR", "artifacts/proof"))
    parser.add_argument("--project", default=None)
    args = parser.parse_args()

    if not args.api_token:
        raise SystemExit("OPERAIQ_API_TOKEN or --api-token is required")

    generated_at = datetime.now(timezone.utc)
    project = args.project or f"checkout-live-proof-{generated_at.strftime('%Y%m%d%H%M%S')}"
    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    source_base_url = f"http://127.0.0.1:{args.source_app_port}"
    env = {
        **os.environ,
        "OPERAIQ_BASE_URL": args.operaiq_base_url.rstrip("/"),
        "OPERAIQ_API_TOKEN": args.api_token,
        "SOURCE_APP_ORG_ID": "acme-retail",
        "SOURCE_APP_PROJECT": project,
    }
    checks: list[dict[str, object]] = []
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "examples.failing_checkout_app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.source_app_port),
            "--log-level",
            "warning",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_source_app(source_base_url)
        with httpx.Client(base_url=args.operaiq_base_url.rstrip("/"), timeout=60.0) as operaiq:
            seed = operaiq.post(
                "/api/seed",
                params={"reset": "false"},
                headers={"Authorization": f"Bearer {args.api_token}"},
            )
            seed_json = seed.json()
            record(
                checks,
                "operaiq_seeded_public_qdrant_memory",
                seed.status_code == 200 and seed_json.get("tenantPointCount", 0) >= 8,
                seed_json,
            )

            readiness = operaiq.get("/runtime/readiness")
            readiness_json = readiness.json()
            record(
                checks,
                "operaiq_public_readiness_before_failure",
                readiness.status_code == 200 and readiness_json.get("ready") is True,
                readiness_json,
            )

        checkout = httpx.post(
            f"{source_base_url}/checkout",
            json={"orderId": f"order-{generated_at.strftime('%H%M%S')}", "amountCents": 12900},
            timeout=90.0,
        )
        checkout_json = checkout.json()
        record(
            checks,
            "source_app_failed_and_delivered_event",
            checkout.status_code == 503 and checkout_json.get("operaiqAccepted") is True,
            checkout_json,
        )

        last = httpx.get(f"{source_base_url}/last-incident", timeout=10.0)
        last_json = last.json()
        result = (last_json.get("operaiqResult") or {}).get("resolution") or {}
        record(
            checks,
            "operaiq_autonomous_response_completed",
            result.get("match", {}).get("incidentId") == "inc-redis-econnreset-2026-05-21"
            and result.get("recommendation") == "rotate_connection_pool"
            and result.get("verification", {}).get("verified") is True
            and (result.get("learnedIncident") or {}).get("orgId") == "acme-retail",
            last_json,
        )

        with httpx.Client(base_url=args.operaiq_base_url.rstrip("/"), timeout=60.0) as operaiq:
            final_readiness = operaiq.get("/runtime/readiness").json()
            record(
                checks,
                "operaiq_public_readiness_after_failure",
                final_readiness.get("ready") is True and final_readiness.get("qdrant", {}).get("mode") == "server",
                final_readiness,
            )

        artifact = {
            "app": "OperaIQ",
            "sourceApp": "failing-checkout",
            "operaiqBaseUrl": args.operaiq_base_url.rstrip("/"),
            "sourceAppBaseUrl": source_base_url,
            "project": project,
            "generatedAt": generated_at.isoformat(),
            "accepted": all(check["passed"] for check in checks),
            "checks": checks,
            "proofSummary": {
                "flow": "failing checkout app -> signed OperaIQ webhook -> Qdrant recall -> autonomous response -> learned memory",
                "sourceStatus": checkout.status_code,
                "sourceEventId": checkout_json.get("sourceEventId"),
                "matchedIncident": result.get("match", {}).get("incidentId"),
                "recommendedAction": result.get("recommendation"),
                "verified": result.get("verification", {}).get("verified"),
                "tenantPointCount": result.get("tenantPointCount"),
            },
        }
        artifact_path = artifact_dir / f"operaiq-failing-app-flow-{generated_at.strftime('%Y%m%d%H%M%S')}.json"
        artifact_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

        print(f"accepted={artifact['accepted']}")
        print(f"artifact={artifact_path}")
        print(f"operaiq_base_url={artifact['operaiqBaseUrl']}")
        print(f"source_status={checkout.status_code}")
        print(f"matched_incident={artifact['proofSummary']['matchedIncident']}")
        print(f"recommended_action={artifact['proofSummary']['recommendedAction']}")
        print(f"verified={artifact['proofSummary']['verified']}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=8)


if __name__ == "__main__":
    main()
