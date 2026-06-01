from __future__ import annotations

import hashlib
import hmac
from urllib.parse import quote

from fastapi import HTTPException, Request

from app.config import Settings


DEV_WEBHOOK_SECRET = "operaiq-development-webhook-secret"


def webhook_secret(settings: Settings) -> str:
    if settings.operaiq_webhook_secret:
        return settings.operaiq_webhook_secret
    if settings.is_production:
        raise HTTPException(status_code=503, detail="webhook secret is not configured")
    return DEV_WEBHOOK_SECRET


def webhook_signature(secret: str, org_id: str, project: str) -> str:
    payload = f"{org_id}:{project}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()[:40]


def verify_webhook_signature(secret: str, org_id: str, project: str, signature: str) -> bool:
    expected = webhook_signature(secret, org_id, project)
    return hmac.compare_digest(expected, signature)


def webhook_path(org_id: str, project: str, secret: str) -> str:
    safe_org = quote(org_id, safe="")
    safe_project = quote(project, safe="")
    signature = webhook_signature(secret, org_id, project)
    return f"/api/webhooks/{safe_org}/{safe_project}/{signature}"


def webhook_url(request: Request, settings: Settings, path: str) -> str:
    base_url = settings.operaiq_public_url or str(request.base_url)
    return f"{base_url.rstrip('/')}{path}"
