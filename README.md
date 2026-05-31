# Sentinel Memory Layer

Fresh MVP for the Qdrant side quest. This is not the current Sentinel repo.

The demo shows Qdrant as Sentinel's incident memory layer:

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

Optional Qdrant server:

```bash
docker compose up -d qdrant
QDRANT_URL=http://localhost:6333 uv run python -m app.cli
```

Note: `QDRANT_URL=:memory:` is useful for fast local demos, but Qdrant warns that payload indexes do not affect local embedded mode. Use Docker/Qdrant Cloud for true indexed-filter performance proof.

## Test

```bash
uv run ruff check .
uv run pytest
```

## Honest build status

Core MVP is intentionally narrow: one alert, one recall loop, one verification story, and one learning write-back. It is built as a submission-sized Qdrant demo, not a replacement for Splunk and not a fork of Sentinel.
