# OperaIQ

**Autonomous incident response powered by Qdrant memory.**

OperaIQ is an incident response agent, not a standalone search page and not only a memory store. It gives production apps a signed webhook URL. When a source system sends a failure event, OperaIQ stores the signal in Qdrant, recalls the closest resolved incident for that tenant, chooses the action that worked before, verifies the signal changed, and writes the new resolved incident back into Qdrant.

Qdrant is the memory layer. OperaIQ is the response loop around it.

---

## Production Flow

```text
Your app / observability source
  -> POST signed OperaIQ webhook URL
  -> OperaIQ stores the source event as unresolved Qdrant signal memory
  -> OperaIQ recalls resolved incidents with orgId-filtered vector search
  -> OperaIQ selects the prior action that worked
  -> OperaIQ verifies the response signal
  -> OperaIQ writes the learned incident back into Qdrant
  -> the next matching incident starts with stronger memory
```

The dashboard exposes this flow directly:

- Generate a signed webhook URL for an org/project.
- Copy that URL into the source app or observability system.
- Send a source event through the generated URL.
- Use `Resolve alert` only as the operator fallback for a known alert payload.
- Check readiness, payload indexes, tenant isolation, verification, and learned write-back.

---

## Why Qdrant Matters

Every resolved incident becomes a Qdrant point with a vector and structured payload:

- `orgId`, `project`, `service`, `severity`, `resolved`, `createdAt`
- symptoms and root cause
- resolution and action taken
- verification result from the latest incident

Before OperaIQ responds to a new event, it filters by `orgId` and `resolved=true`, then searches for the closest proven fix. After handling the incident, it writes the new outcome back as another resolved memory. That is the learning loop.

---

## Runtime Shape

Preferred hosted path:

```text
Render web service
  -> OperaIQ FastAPI app
  -> Qdrant Cloud or another hosted Qdrant server
  -> collection: incident_memories
```

Fallback server path:

```text
EC2 / Docker Compose
  -> OperaIQ app container
  -> private Qdrant container with persistent storage and API key
```

Do not use in-memory Qdrant for production. `/runtime/readiness` reports unsafe runtime state when `QDRANT_URL=:memory:`.

Current hosted deployment:

- Public app: `https://operaiq.onrender.com`
- Runtime: Render web service, independent of the local terminal.
- Memory: hosted/server Qdrant collection `incident_memories`.
- Current readiness: production `ready=true`, Qdrant mode `server`, vector size `384`, and payload indexes for `createdAt`, `kind`, `orgId`, `project`, `resolved`, `service`, and `severity`.
- Local proof scripts and local source apps stop when the PC is off. The public Render app and hosted Qdrant do not depend on the PC staying on.

---

## Production Controls

- `/api/integrations/webhook` generates a signed per-org/project webhook URL.
- `/api/webhooks/{orgId}/{project}/{signature}` accepts source events without exposing the operator token.
- `/api/incidents/latest?orgId=<org>` lets the dashboard show the newest resolved Qdrant memory after an external source app posts a failure event.
- `OPERAIQ_WEBHOOK_SECRET` signs generated webhook URLs and rotates them when changed.
- `OPERAIQ_API_TOKEN` protects operator/admin write paths.
- `/health` reports app state, Qdrant mode, collection status, payload indexes, vector size, and tenant point count.
- `/runtime/readiness` reports production blockers and warnings.
- `ALLOW_UNAUTHENTICATED_WRITES=false` is the production default.
- `ALLOW_COLLECTION_RESET=false` prevents public collection resets.

Required environment:

```env
APP_ENV=production
OPERAIQ_PUBLIC_URL=https://<operaiq-host>
QDRANT_URL=https://<qdrant-host>
QDRANT_API_KEY=<secret>
QDRANT_COLLECTION=incident_memories
OPERAIQ_API_TOKEN=<secret>
OPERAIQ_WEBHOOK_SECRET=<secret>
ALLOW_UNAUTHENTICATED_WRITES=false
ALLOW_COLLECTION_RESET=false
```

Use `.env.production.example` for Render/Qdrant Cloud and `.env.aws.example` for the Docker fallback.

---

## Run Locally

```bash
cp .env.example .env
uv sync
uv run python -m app.cli
uv run uvicorn app.main:app --reload --port 8097
```

Open `http://127.0.0.1:8097`.

For Qdrant server mode:

```bash
docker compose up -d
```

The CLI path proves the learning loop without relying on browser-only state:

```bash
uv run python -m app.cli --project local-checkout-flow
```

Expected shape:

```text
Your app -> signed OperaIQ webhook -> Qdrant memory -> autonomous response -> learned memory
webhook_path=/api/webhooks/acme-payments/local-checkout-flow/<signature>
recalled_incident=inc-redis-econnreset-2026-05-21
recommended_action=rotate_connection_pool
learned_incident=...
```

---

## API Surface

| Route | Purpose |
|---|---|
| `POST /api/integrations/webhook` | Generates a signed webhook URL for an org/project. |
| `POST /api/webhooks/{orgId}/{project}/{signature}` | Receives source events, recalls memory, verifies response, and writes learned memory. |
| `GET /api/incidents/latest?orgId=<org>` | Reads the newest resolved incident memory for the dashboard. |
| `POST /api/alerts/resolve` | Operator fallback for resolving an existing alert payload. |
| `POST /api/seed?reset=false` | Idempotently creates baseline resolved memory. Reset is blocked unless explicitly enabled. |
| `POST /api/app/logs` | Internal/source-log intake for unresolved signal memory. |
| `POST /api/qdrant/watch` | Internal watcher path for unresolved Qdrant signal memory. |
| `GET /health` | Deploy health. |
| `GET /runtime/readiness` | Production truth check. |

---

## Verification

```bash
uv run ruff check .
uv run python -m pytest
uv run python -m compileall app scripts tests
docker compose config
QDRANT_API_KEY="$(openssl rand -hex 24)" \
OPERAIQ_API_TOKEN="$(openssl rand -hex 24)" \
OPERAIQ_WEBHOOK_SECRET="$(openssl rand -hex 24)" \
docker compose --env-file .env.aws.example -f docker-compose.aws.yml config >/tmp/operaiq-aws-compose.yml
uv run python scripts/operaiq_human_flow.py --base-url http://127.0.0.1:8097
```

The proof script checks UI load, seed without reset, readiness, signed webhook generation, source webhook delivery, Qdrant recall/write-back, and Globex tenant isolation. Artifacts are written under `artifacts/proof/` and ignored by Git.

For a source-app proof, run a failing checkout app against the hosted OperaIQ URL:

```bash
OPERAIQ_BASE_URL=https://operaiq.onrender.com \
OPERAIQ_API_TOKEN=<operator token> \
uv run python scripts/prove_failing_app_flow.py --operaiq-base-url https://operaiq.onrender.com
```

That script starts the checkout source app, lets `/checkout` return a real `503`, sends the source event through the signed OperaIQ webhook, and verifies Qdrant recall, action selection, verification, and learned-memory write-back.

---

## Deployment

- Render app playbook: `deploy/render/README.md`
- Docker fallback: `deploy/aws/README.md`
- Operator proof checklist: `PLAYBOOK.md`

---

## Honest State

| Component | State |
|---|---|
| Autonomous source webhook | Implemented with signed per-org/project URLs |
| Qdrant server mode | Verified on hosted public runtime |
| Tenant-filtered recall | Verified |
| Payload indexes | Verified on hosted/server Qdrant |
| Source event intake | Implemented |
| Operator fallback resolve | Implemented |
| Learned memory write-back | Verified |
| Render deployment config | Implemented |
| Hosted Qdrant credentials | Set in deploy environment, not committed |
| Public Render URL | Live at `https://operaiq.onrender.com` |
| Failing app source proof | Verified: source app `503` -> signed webhook -> Qdrant recall -> autonomous response -> learned memory |
