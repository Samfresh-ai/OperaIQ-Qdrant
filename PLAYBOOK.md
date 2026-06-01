# OperaIQ Production Playbook

## Deployment Order

1. Deploy the OperaIQ app on Render from `render.yaml`.
2. Point `QDRANT_URL` at Qdrant Cloud or a hosted Qdrant server.
3. Set `QDRANT_API_KEY`, `OPERAIQ_API_TOKEN`, and `OPERAIQ_WEBHOOK_SECRET` as secrets.
4. Keep `ALLOW_UNAUTHENTICATED_WRITES=false`.
5. Keep `ALLOW_COLLECTION_RESET=false`.
6. Run the proof script from a trusted machine.

## Preflight

```bash
uv run ruff check .
uv run python -m pytest
uv run python -m compileall app scripts tests
docker compose config
QDRANT_API_KEY="$(openssl rand -hex 24)" \
OPERAIQ_API_TOKEN="$(openssl rand -hex 24)" \
OPERAIQ_WEBHOOK_SECRET="$(openssl rand -hex 24)" \
docker compose --env-file .env.aws.example -f docker-compose.aws.yml config >/tmp/operaiq-aws-compose.yml
```

## Runtime Proof

Local server-mode proof:

```bash
docker compose up -d
OPERAIQ_API_TOKEN=local-compose-token \
OPERAIQ_WEBHOOK_SECRET=local-webhook-secret \
uv run python scripts/operaiq_human_flow.py --base-url http://127.0.0.1:8097
```

Render proof:

```bash
OPERAIQ_API_TOKEN=<render-secret> \
uv run python scripts/operaiq_human_flow.py --base-url https://<operaiq-render-url>
```

Failing source-app proof:

```bash
OPERAIQ_API_TOKEN=<render-secret> \
uv run python scripts/prove_failing_app_flow.py --operaiq-base-url https://<operaiq-render-url>
```

Proof must show:

- UI loads.
- `/health` returns `status=ok`.
- `/runtime/readiness` returns `ready=true`.
- Signed webhook URL is generated for the org/project.
- Source event is accepted through the generated webhook URL.
- A separate checkout source app returns `503` and emits the event to OperaIQ.
- OperaIQ writes the source event into Qdrant as unresolved signal memory.
- OperaIQ recalls the closest resolved incident and responds.
- Acme recall resolves to `inc-redis-econnreset-2026-05-21`.
- Recommended action is `rotate_connection_pool`.
- Learned memory writes back to Qdrant.
- Globex recall resolves to `inc-redis-econnreset-globex-2026-05-23`, not Acme memory.

## Local CLI Check

Use this when someone wants to test the learning loop on a local machine:

```bash
uv sync
uv run python -m app.cli --project local-checkout-flow
```

The CLI should print:

```text
Your app -> signed OperaIQ webhook -> Qdrant memory -> autonomous response -> learned memory
webhook_path=/api/webhooks/acme-payments/local-checkout-flow/<signature>
recalled_incident=inc-redis-econnreset-2026-05-21
recommended_action=rotate_connection_pool
learned_incident=...
```

## Production Readiness Kill Criteria

Stop and fix before shipping if any are true:

- `/runtime/readiness` has issues.
- `qdrant.mode` is `memory`.
- `missingIndexes` is not empty in server mode.
- `OPERAIQ_API_TOKEN` is unset.
- `OPERAIQ_WEBHOOK_SECRET` is unset.
- `ALLOW_UNAUTHENTICATED_WRITES=true`.
- `ALLOW_COLLECTION_RESET=true`.
- Qdrant server has no persistent storage.
- Qdrant API is public without TLS and an API key.
- Tenant-isolation proof does not pass.
- The proof script does not show signed webhook -> Qdrant recall -> autonomous response -> learned memory write-back.
