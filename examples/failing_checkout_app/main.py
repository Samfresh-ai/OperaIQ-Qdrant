from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from starlette.responses import JSONResponse
import httpx


class CheckoutRequest(BaseModel):
    orderId: str
    customerId: str = "customer-live-proof"
    amountCents: int = 12900


class SourceState:
    webhook_url: str | None = None
    webhook_path: str | None = None
    last_operaiq_result: dict[str, Any] | None = None
    last_failure: dict[str, Any] | None = None


app = FastAPI(title="OperaIQ failing checkout source")
state = SourceState()


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def source_project() -> str:
    return os.getenv("SOURCE_APP_PROJECT", "checkout-live-failure")


def source_org() -> str:
    return os.getenv("SOURCE_APP_ORG_ID", "acme-retail")


async def ensure_webhook() -> str:
    if state.webhook_url:
        return state.webhook_url

    base_url = required_env("OPERAIQ_BASE_URL").rstrip("/")
    api_token = required_env("OPERAIQ_API_TOKEN")
    async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as client:
        response = await client.post(
            "/api/integrations/webhook",
            headers={"Authorization": f"Bearer {api_token}"},
            json={"orgId": source_org(), "project": source_project()},
        )
    response.raise_for_status()
    body = response.json()
    state.webhook_url = str(body["webhookUrl"])
    state.webhook_path = str(body["webhookPath"])
    return state.webhook_url


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "sourceApp": "failing-checkout",
        "operaiqBaseUrl": os.getenv("OPERAIQ_BASE_URL"),
        "webhookRegistered": state.webhook_url is not None,
        "project": source_project(),
    }


@app.post("/checkout")
async def checkout(request: CheckoutRequest) -> JSONResponse:
    webhook_url = await ensure_webhook()
    now = datetime.now(timezone.utc)
    source_event = {
        "eventId": f"checkout-failure-{request.orderId}-{int(now.timestamp())}",
        "service": "checkout-api",
        "severity": "sev1",
        "message": (
            "Redis ECONNRESET burst from checkout-api during payment authorization; "
            "error rate spiked and p95 latency exceeded five seconds."
        ),
        "observedAt": now.isoformat(),
        "errorCount": 327,
        "p95LatencyMs": 5120,
    }
    state.last_failure = {
        "orderId": request.orderId,
        "customerId": request.customerId,
        "amountCents": request.amountCents,
        "sourceEventId": source_event["eventId"],
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(webhook_url, json=source_event)

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"OperaIQ webhook rejected source event with {response.status_code}",
        )

    state.last_operaiq_result = response.json()
    result = state.last_operaiq_result.get("resolution", {})
    match = result.get("match", {})
    verification = result.get("verification", {})
    return JSONResponse(
        status_code=503,
        content={
            "status": "checkout_failed",
            "orderId": request.orderId,
            "sourceEventId": source_event["eventId"],
            "operaiqAccepted": state.last_operaiq_result.get("webhookAccepted") is True,
            "operaiqAction": result.get("recommendation"),
            "matchedIncident": match.get("incidentId"),
            "verified": verification.get("verified") is True,
        },
    )


@app.get("/last-incident")
async def last_incident() -> dict[str, object]:
    return {
        "sourceFailure": state.last_failure,
        "webhookRegistered": state.webhook_url is not None,
        "webhookPath": state.webhook_path,
        "operaiqResult": state.last_operaiq_result,
    }
