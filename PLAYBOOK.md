# OperaIQ Production Playbook

## Deployment Order

1. Deploy the OperaIQ app on Render from `render.yaml`.
2. Point `QDRANT_URL` at Qdrant Cloud or a hosted Qdrant server.
3. Set `QDRANT_API_KEY` and `OPERAIQ_API_TOKEN` as secrets.
4. Keep `ALLOW_UNAUTHENTICATED_WRITES=false`.
5. Keep `ALLOW_COLLECTION_RESET=false`.
6. Run the proof script from a trusted machine.

## Preflight

```bash
uv run ruff check .
uv run python -m pytest
uv run python -m compileall app scripts tests
docker compose config
QDRANT_API_KEY=dummy OPERAIQ_API_TOKEN=dummy docker compose --env-file .env.aws.example -f docker-compose.aws.yml config
```

## Runtime Proof

Local server-mode proof:

```bash
docker compose up -d
OPERAIQ_API_TOKEN=local-compose-token \
uv run python scripts/operaiq_human_flow.py --base-url http://127.0.0.1:8097
```

Render proof:

```bash
OPERAIQ_API_TOKEN=<render-secret> \
uv run python scripts/operaiq_human_flow.py --base-url https://<operaiq-render-url>
```

Proof must show:

- UI loads.
- `/health` returns `status=ok`.
- `/runtime/readiness` returns `ready=true`.
- App failure logs write into Qdrant as unresolved signal memory.
- OperaIQ watcher finds the Qdrant pattern and fires `/api/webhooks/pattern-alert`.
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
Your app -> Qdrant app-log memory -> watcher webhook -> OperaIQ -> Qdrant learned memory
webhook_path=/api/webhooks/pattern-alert
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
- `ALLOW_UNAUTHENTICATED_WRITES=true`.
- `ALLOW_COLLECTION_RESET=true`.
- Qdrant server has no persistent storage.
- Qdrant API is public without TLS and an API key.
- Tenant-isolation proof does not pass.
- The proof script does not show app logs -> Qdrant watcher -> webhook -> learned memory write-back.
