# OperaIQ Production Playbook

## Deployment Order

1. Deploy the OperaIQ app on Render from `render.yaml`.
2. Point `QDRANT_URL` at Qdrant Cloud or a hosted Qdrant server.
3. Set `QDRANT_API_KEY` and `OPERAIQ_API_TOKEN` as secrets.
4. Keep `ALLOW_UNAUTHENTICATED_WRITES=false`.
5. Keep `ALLOW_JUDGE_QUICK_RUN=true` only when judges need a no-setup check.
6. Keep `ALLOW_JUDGE_RESET=false` unless you are deliberately cleaning the collection before a private proof run.

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
- Acme alert recalls `inc-redis-econnreset-2026-05-21`.
- Recommended action is `rotate_connection_pool`.
- A learned memory writes back.
- Globex alert recalls `inc-redis-econnreset-globex-2026-05-23`, not Acme memory.

## Judge Fallback

When the full hosted setup is available but a judge wants the fastest path:

```bash
curl -X POST https://<operaiq-url>/api/judge/quick-run
```

This is intentionally narrow. It does not unlock arbitrary writes and it does not reset the collection.

## Production Readiness Kill Criteria

Stop and fix before submission if any are true:

- `/runtime/readiness` has issues.
- `qdrant.mode` is `memory`.
- `missingIndexes` is not empty in server mode.
- `OPERAIQ_API_TOKEN` is unset.
- `ALLOW_UNAUTHENTICATED_WRITES=true`.
- Qdrant server has no persistent storage.
- Qdrant API is public without TLS and an API key.
- Tenant-isolation proof does not pass.
