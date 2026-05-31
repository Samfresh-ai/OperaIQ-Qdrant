# OperaIQ

**Incident memory for ops agents, backed by Qdrant.**

OperaIQ stores resolved incidents as vector points with structured payloads. When a new Splunk-style alert arrives, it embeds the alert, filters Qdrant by `orgId`, recalls the closest proven fix, verifies the action signal, and writes the newly resolved memory back to the collection.

## Live Deployment Shape

Preferred production path:

```text
Render web service
  -> OperaIQ FastAPI app
  -> Qdrant Cloud or another hosted Qdrant server
  -> collection: incident_memories
```

Fallback AWS path:

```text
EC2 / Docker Compose
  -> OperaIQ app container
  -> private Qdrant container with persistent storage and API key
```

Do not use in-memory Qdrant for production. `/runtime/readiness` marks production unsafe when `QDRANT_URL=:memory:`.

## What It Proves

1. Resolved postmortems are stored as Qdrant points: dense vector plus payload.
2. Payload indexes are created for `orgId`, `service`, `severity`, `resolved`, and `createdAt`.
3. Tenant recall is filtered by `orgId`; one tenant does not retrieve another tenant's memory.
4. A new alert retrieves the closest resolved incident and recommends the action that worked before.
5. The resolved alert is written back as a new memory, so the collection learns over time.

## Production Controls

- `/health` reports app state, Qdrant mode, collection status, payload indexes, vector size, and tenant point count.
- `/runtime/readiness` reports production blockers and warnings.
- Normal write paths require `OPERAIQ_API_TOKEN` in production.
- `ALLOW_UNAUTHENTICATED_WRITES=false` is the production default.
- `ALLOW_JUDGE_QUICK_RUN=true` keeps a limited quick-run path available for judges without setup.
- `ALLOW_JUDGE_RESET=false` prevents public collection resets.

## Required Environment

```env
APP_ENV=production
QDRANT_URL=https://<qdrant-host>
QDRANT_API_KEY=<secret>
QDRANT_COLLECTION=incident_memories
OPERAIQ_API_TOKEN=<secret>
ALLOW_UNAUTHENTICATED_WRITES=false
ALLOW_JUDGE_QUICK_RUN=true
ALLOW_JUDGE_RESET=false
```

Use `.env.production.example` for Render/Qdrant Cloud and `.env.aws.example` for the AWS Compose fallback.

## Run Locally

```bash
cp .env.example .env
uv sync
uv run python -m app.cli
uv run uvicorn app.main:app --reload --port 8097
```

Open `http://127.0.0.1:8097`.

Local server mode:

```bash
docker compose up -d
```

## Optional Judge Quick-Run

For a no-setup judge check:

```bash
uv sync
uv run python -m app.cli
uv run uvicorn app.main:app --port 8097
uv run python scripts/operaiq_human_flow.py --base-url http://127.0.0.1:8097
```

Production quick-run endpoint:

```bash
curl -X POST https://<operaiq-url>/api/judge/quick-run
```

That path seeds the baseline incident memories if needed, resolves the default alert, verifies tenant-filtered recall, and writes one learned memory back.

## Deployment

- Render app playbook: `deploy/render/README.md`
- AWS hosted Qdrant fallback: `deploy/aws/README.md`
- Operator proof checklist: `PLAYBOOK.md`

## Verification

```bash
uv run ruff check .
uv run python -m pytest
uv run python -m compileall app scripts tests
docker compose config
QDRANT_API_KEY=dummy OPERAIQ_API_TOKEN=dummy docker compose --env-file .env.aws.example -f docker-compose.aws.yml config
uv run python scripts/operaiq_human_flow.py --base-url http://127.0.0.1:8097
```

The strict proof script checks UI load, seed, health, readiness, Acme recall/write-back, and Globex tenant isolation. Proof artifacts are written under `artifacts/proof/` and ignored by Git.

## Honest State

| Component | State |
|---|---|
| Qdrant server mode | Verified locally with official Qdrant server |
| Tenant-filtered recall | Verified |
| Payload indexes | Verified in server mode |
| Learned memory write-back | Verified |
| Render deployment config | Implemented |
| AWS Qdrant Compose fallback | Implemented |
| Qdrant Cloud live cluster | Ready for credentials; not committed |
| Public Render URL | Requires creating the Render service from `render.yaml` |
