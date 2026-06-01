from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_exposes_alert_webhook_and_proof_sections() -> None:
    html = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")

    assert 'href="#incidents"' in html
    assert 'href="#services"' in html
    assert 'href="#proof"' in html
    assert 'id="generate-webhook"' in html
    assert 'id="send-source-event"' not in html
    assert 'id="fire-' + 'webhook"' not in html
    assert "Agent Reasoning Panel" in html


def test_dashboard_never_resets_seed_from_browser_flow() -> None:
    javascript = (ROOT / "app/static/app.js").read_text(encoding="utf-8")

    assert "/api/seed?reset=true" not in javascript
    assert 'postJson("/api/seed?reset=false")' in javascript

    resolve_start = javascript.index("async function resolveCurrentAlert()")
    webhook_start = javascript.index("function integrationMatchesForm")
    resolve_body = javascript[resolve_start:webhook_start]

    assert "/api/seed" not in resolve_body
    assert "assertMemoryReady()" in resolve_body
    assert "sendSourceEvent" not in javascript


def test_dashboard_generates_signed_webhook_before_source_delivery() -> None:
    javascript = (ROOT / "app/static/app.js").read_text(encoding="utf-8")

    assert 'postJson("/api/integrations/webhook", integrationPayload())' in javascript
    assert "activeWebhookIntegration" in javascript
    assert "sourceWebhookPayload" not in javascript


def test_dashboard_payload_index_evidence_matches_runtime_indexes() -> None:
    javascript = (ROOT / "app/static/app.js").read_text(encoding="utf-8")

    assert "createdAt, kind, orgId, project, resolved, service, severity" in javascript


def test_failing_source_app_flow_exists_without_dashboard_source_button() -> None:
    source_app = (ROOT / "examples/failing_checkout_app/main.py").read_text(encoding="utf-8")
    proof_script = (ROOT / "scripts/prove_failing_app_flow.py").read_text(encoding="utf-8")

    assert "/api/integrations/webhook" in source_app
    assert "/checkout" in source_app
    assert "status_code=503" in source_app
    assert "failing checkout app -> signed OperaIQ webhook" in proof_script
