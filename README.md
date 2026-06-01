# OperaIQ

**Incident memory for ops agents, backed by Qdrant.**

> *The incident brain that remembers what worked.*

OperaIQ sits after your observability stack. When an app failure pattern appears, it stores the raw signal in Qdrant, recalls similar resolved incidents with tenant-filtered vector search, chooses the action that worked before, verifies the signal changed, and writes the newly resolved incident back into Qdrant.

The point is simple: the next similar failure should not start from zero.

---

## The Flow

```text
Your app
  -> app failure logs stored in Qdrant as unresolved signal memory
  -> OperaIQ watcher scans Qdrant for unresolved patterns
  -> watcher fires /api/webhooks/pattern-alert
  -> OperaIQ recalls the closest resolved incident for that org
  -> OperaIQ verifies the action signal
  -> resolved incident writes back into Qdrant
  -> the next matching incident resolves with better memory
```

Qdrant is the memory and recall layer. OperaIQ owns the watcher/webhook step because Qdrant does not run arbitrary remediation code by itself.

---

## Why It Learns

Every resolved incident becomes a Qdrant point with a vector and structured payload:

- `orgId`, `service`, `severity`, `resolved`, `createdAt`
- symptoms and root cause
- resolution and action taken
- verification result from the latest incident

Before acting on a new alert, OperaIQ filters by `orgId` and `resolved=true`, then searches for the closest proven fix. After the incident is handled, the new resolution is written back as another point. That is the learning loop.

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

---

## Production Controls

- `/health` reports app state, Qdrant mode, collection status, payload indexes, vector size, and tenant point count.
- `/runtime/readiness` reports production blockers and warnings.
- Normal write paths require `OPERAIQ_API_TOKEN` in production.
- `ALLOW_UNAUTHENTICATED_WRITES=false` is the production default.
- `ALLOW_COLLECTION_RESET=false` prevents public collection resets.
- There is no browser demo endpoint. Local demo/proof runs through the CLI or proof script.

Required environment:

```env
APP_ENV=production
QDRANT_URL=https://<qdrant-host>
QDRANT_API_KEY=<secret>
QDRANT_COLLECTION=incident_memories
OPERAIQ_API_TOKEN=<secret>
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

The CLI path proves the full learning loop without a browser reset button:

```bash
uv run python -m app.cli --project local-checkout-flow
```

Expected shape:

```text
Your app -> Qdrant app-log memory -> watcher webhook -> OperaIQ -> Qdrant learned memory
logged_event=...
webhook_path=/api/webhooks/pattern-alert
recalled_incident=inc-redis-econnreset-2026-05-21
recommended_action=rotate_connection_pool
learned_incident=...
```

---

## API Surface

| Route | Purpose |
|---|---|
| `POST /api/seed?reset=false` | Idempotently creates baseline resolved memory. Reset is blocked unless explicitly enabled. |
| `POST /api/app/logs` | Stores app failure logs in Qdrant as unresolved signal memory. |
| `POST /api/qdrant/watch` | Finds unresolved Qdrant signal memory and fires the pattern webhook path. |
| `POST /api/webhooks/pattern-alert` | Resolves a pattern alert and writes learned memory back to Qdrant. |
| `POST /api/alerts/resolve` | Direct resolve path for an existing alert payload. |
| `GET /health` | Deploy health. |
| `GET /runtime/readiness` | Production truth check. |

---

## Verification

```bash
uv run ruff check .
uv run python -m pytest
uv run python -m compileall app scripts tests
docker compose config
QDRANT_API_KEY=dummy OPERAIQ_API_TOKEN=dummy docker compose --env-file .env.aws.example -f docker-compose.aws.yml config
uv run python scripts/operaiq_human_flow.py --base-url http://127.0.0.1:8097
```

The proof script checks UI load, seed without reset, readiness, app-log ingestion, Qdrant watcher, webhook firing, Acme recall/write-back, and Globex tenant isolation. Artifacts are written under `artifacts/proof/` and ignored by Git.

---

## Deployment

- Render app playbook: `deploy/render/README.md`
- Docker fallback: `deploy/aws/README.md`
- Operator proof checklist: `PLAYBOOK.md`

---

## Honest State

| Component | State |
|---|---|
| Qdrant server mode | Verified locally with official Qdrant server |
| Tenant-filtered recall | Verified |
| Payload indexes | Verified in server mode |
| App-log ingestion | Implemented |
| Qdrant watcher + webhook path | Implemented in OperaIQ |
| Learned memory write-back | Verified |
| Render deployment config | Implemented |
| Hosted Qdrant credentials | Not committed; set in deploy environment |
| Public Render URL | Requires creating the Render service from `render.yaml` |
