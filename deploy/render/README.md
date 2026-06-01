# OperaIQ Render Deployment

Render hosts the OperaIQ app. Qdrant should live outside the Render web container: use Qdrant Cloud first, or another hosted Qdrant server with TLS and an API key.

## Preferred Shape

- `operaiq`: Docker web service from the repo root `Dockerfile`.
- Instance type: `free` in `render.yaml` for the no-card hosted path; upgrade before relying on it for production traffic.
- Health check path: `/health`.
- Readiness path: `/runtime/readiness`.
- Vector store: Qdrant Cloud or hosted Qdrant server.
- Write protection: `OPERAIQ_API_TOKEN` on every production write path.
- Inbound incident source: signed webhook URLs generated with `OPERAIQ_WEBHOOK_SECRET`.

## Required Variables

```text
APP_NAME=OperaIQ
APP_ENV=production
OPERAIQ_PUBLIC_URL=https://<operaiq-render-url>
QDRANT_URL=https://<cluster>.<region>.<provider>.cloud.qdrant.io
QDRANT_API_KEY=<secret>
QDRANT_COLLECTION=incident_memories
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
OPERAIQ_API_TOKEN=<generated secret>
OPERAIQ_WEBHOOK_SECRET=<generated secret>
ALLOW_UNAUTHENTICATED_WRITES=false
ALLOW_COLLECTION_RESET=false
PROOF_ARTIFACTS_DIR=artifacts/proof
```

`render.yaml` prompts for `QDRANT_URL` and `QDRANT_API_KEY`, generates `OPERAIQ_API_TOKEN` and `OPERAIQ_WEBHOOK_SECRET`, sets `/health` as the HTTP health check, and uses Render's free web instance so the service can be created without adding billing details.

## Qdrant Cloud Target

Create the Qdrant Cloud cluster, copy the cluster URL and database API key, then set:

```text
QDRANT_URL=https://<cluster-url>
QDRANT_API_KEY=<database-api-key>
```

Do not use a Qdrant Cloud management key as the app's database key. The app needs database access to one cluster, not account-level management permissions.

## Deploy

1. Push the repo to GitHub.
2. In Render, create a new Blueprint from this repo.
3. Fill `QDRANT_URL` and `QDRANT_API_KEY` when prompted.
4. Wait for the Docker deploy to pass `/health`.
5. Open `/runtime/readiness`; production must be `true` and ready must be `true`.

## Proof

Run this from a trusted machine after the deploy:

```bash
OPERAIQ_API_TOKEN=<secret> \
uv run python scripts/operaiq_human_flow.py --base-url https://<operaiq-render-url>
```

Required flow:

```text
UI loads -> signed webhook URL generated -> source event accepted -> Qdrant recall runs -> OperaIQ responds -> learned memory writes back -> Globex tenant recall stays isolated
```

## Monitoring

Monitor both:

```text
GET https://<operaiq-render-url>/health
GET https://<operaiq-render-url>/runtime/readiness
```

`/health` is the Render deploy health check. `/runtime/readiness` is the product truth check; do not treat a deploy as ready until it passes.
