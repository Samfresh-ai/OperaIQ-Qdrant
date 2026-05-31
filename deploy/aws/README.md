# OperaIQ AWS Qdrant Fallback

Use this when Qdrant Cloud is not available and OperaIQ needs a durable hosted Qdrant server. This is the fallback shape, not the preferred Render path.

## Shape

```text
EC2 host
  -> OperaIQ app container, public port 8097
  -> Qdrant container, private Docker network only
  -> named Docker volumes for storage and snapshots
```

Qdrant is protected with `QDRANT__SERVICE__API_KEY`. Do not expose port `6333` publicly unless it sits behind TLS and access control.

## Setup

```bash
cp .env.aws.example .env.aws
# fill QDRANT_API_KEY and OPERAIQ_API_TOKEN
docker compose --env-file .env.aws -f docker-compose.aws.yml up -d --build
```

Then seed and prove:

```bash
OPERAIQ_API_TOKEN=<secret> \
uv run python scripts/operaiq_human_flow.py --base-url http://<EC2_HOST>:8097
```

## Readiness

```bash
curl http://<EC2_HOST>:8097/health
curl http://<EC2_HOST>:8097/runtime/readiness
```

Required state:

- `production=true`
- `ready=true`
- `qdrant.mode=server`
- `missingIndexes=[]`
- `collection=incident_memories`

## Backups

The Compose file mounts:

- `qdrant-storage` at `/qdrant/storage`
- `qdrant-snapshots` at `/qdrant/snapshots`

For a collection snapshot:

```bash
curl -X POST http://127.0.0.1:6333/collections/incident_memories/snapshots \
  -H "api-key: <QDRANT_API_KEY>"
```

For production, move snapshots to external storage after creation. A snapshot that only exists on the same EC2 disk is not disaster recovery.

## Kill Criteria

Do not call this AWS path production-ready if:

- Qdrant is in memory mode.
- Qdrant storage is not on a persistent volume.
- `OPERAIQ_API_TOKEN` is empty.
- `/runtime/readiness` has issues.
- Port `6333` is open to the internet without TLS and an API key.
