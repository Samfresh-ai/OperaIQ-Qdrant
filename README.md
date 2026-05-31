# OperaIQ

Production-shaped Qdrant side quest. This is a separate repo and does not touch the current Sentinel codebase.

OperaIQ shows Qdrant as an incident memory layer for ops agents:

1. Seed realistic resolved postmortems.
2. Store each memory as a Qdrant point: dense vector + payload.
3. Create payload indexes before ingestion for tenant-filtered search.
4. Accept a Splunk-style alert.
5. Embed the alert and query Qdrant with an `orgId` filter.
6. Recommend the action from the most similar resolved incident.
7. Write the newly resolved incident back to Qdrant so the product learns.

## Why Qdrant fits

- **Points** are exactly the shape we need: a vector for semantic recall plus payload for incident metadata.
- **Payload filters** keep tenant memory isolated with `orgId`.
- **Payload indexes** are created on `orgId`, `service`, `severity`, `resolved`, and `createdAt` before seed ingestion. That matters because filtering after vector search is weak for a multitenant ops product.
- **Hybrid dense + sparse search** is deliberately left as stretch. The shipped MVP uses dense semantic search plus indexed tenant filtering because that is enough to prove the core workflow.

## Run locally

This uses Qdrant's Python client. By default, `.env.example` uses `QDRANT_URL=:memory:` so the demo runs without Docker. For a normal Qdrant server, use Docker or Qdrant Cloud and set `QDRANT_URL`.

```bash
cp .env.example .env
uv sync
uv run python -m app.cli
uv run uvicorn app.main:app --reload --port 8097
```

Then open `http://127.0.0.1:8097`.

Local server shape:

```bash
docker compose up -d
```

For Qdrant Cloud, set `QDRANT_URL` and `QDRANT_API_KEY` in the deploy environment.

## Test

```bash
uv run ruff check .
uv run pytest
uv run python scripts/operaiq_human_flow.py --base-url http://127.0.0.1:8097
```

## Production checks

- `/health` reports app, env, Qdrant mode, collection state, payload indexes, and tenant point count.
- `/runtime/readiness` fails if production is pointed at in-memory Qdrant or if collection/index checks are missing.
- `scripts/operaiq_human_flow.py` runs a browser/API-style proof: UI load, seed, health, readiness, Acme recall/write-back, and Globex tenant isolation.
- The app is not a Splunk replacement and not a Sentinel fork. It is the Qdrant memory layer proof.
