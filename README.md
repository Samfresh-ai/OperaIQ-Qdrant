# OperaIQ

**Autonomous incident response with Qdrant-backed operational memory.**

> The ops agent that remembers what fixed the last failure.

OperaIQ lets a team send application logs into a Qdrant-backed memory layer, detect hard failure patterns, create an incident, act on low-risk remediations, verify the result, and store the postmortem back into memory.

Qdrant is the brain. It stores app logs, incidents, runbooks, service context, audit events, pattern matches, and postmortems in one vector-searchable memory collection. When the same failure appears again, OperaIQ can retrieve the prior incident and reuse the proven fix instead of starting cold.

Important honesty note: Qdrant is not a native webhook runner or alert scheduler. OperaIQ owns that part. The API stores logs in Qdrant, scans unchecked log patterns, and fires its own `/webhooks/qdrant-pattern` endpoint when the evidence crosses the configured threshold.

---

## The flow

```text
Your app logs
  -> OperaIQ API stores the batch in Qdrant
  -> Qdrant pattern watcher finds a repeated hard-failure signature
  -> POST /webhooks/qdrant-pattern
  -> ASSESS -> REMEMBER -> INVESTIGATE -> MAP -> RETRIEVE -> ACT -> VERIFY -> CLOSE
  -> Postmortem stored back in Qdrant
  -> Brain updated. The next matching incident resolves faster.
```

---

## Why it gets smarter

Every resolved incident becomes a reusable memory item. Before acting on a new incident, OperaIQ searches Qdrant for similar past failures, the runbooks used, the root cause, and the verification result.

| Run | Brain state | What changes |
| --- | --- | --- |
| First occurrence | No matching memory | OperaIQ investigates, acts, verifies, and writes the postmortem |
| Second occurrence | Matching Qdrant memory exists | OperaIQ retrieves the prior fix and starts with stronger evidence |

The demo proof path uses a Redis/payment failure because it is easy to inspect: ECONNRESET bursts, checkout failures, connection-pool exhaustion, action, verification, and postmortem storage are all visible in the flow JSON.

---

## Live deployment

- Web: `https://operaiq.onrender.com`
- Test app: `https://operaiq.onrender.com/test-app`
- API: `https://operaiq-api.3.208.71.125.sslip.io`
- Health: `https://operaiq-api.3.208.71.125.sslip.io/health`
- Runtime readiness: `https://operaiq-api.3.208.71.125.sslip.io/runtime/readiness`
- Agent OpenAPI: `https://operaiq-api.3.208.71.125.sslip.io/agent/openapi.json`

The API and Qdrant run on the AWS host. Qdrant is private to the Docker network and accessed by the API with `QDRANT_URL` and `QDRANT_API_KEY`. The public web app calls the public API URL.

---

## What happens during an incident

Each incident streams through eight phases in real time:

| Phase | What OperaIQ does |
| --- | --- |
| **ASSESS** | Parses the incoming OperaIQ alert or Qdrant pattern payload |
| **REMEMBER** | Searches Qdrant for similar incidents and what resolved them |
| **INVESTIGATE** | Pulls current Qdrant memory signals for the affected service and symptoms |
| **MAP** | Reads the service dependency graph and estimates blast radius |
| **RETRIEVE** | Selects a matching runbook from Qdrant or generates and saves one |
| **ACT** | Executes approved low-risk remediations through the configured backend |
| **VERIFY** | Re-checks the Qdrant signals to confirm the failure cooled down |
| **CLOSE** | Writes the structured postmortem and audit trail back into Qdrant |

If the match confidence is too low or repeated remediation attempts fail, OperaIQ escalates instead of pretending it fixed the issue.

---

## Architecture

```text
Browser test app / user app
        |
        v
POST /projects/:id/logs
        |
        v
Qdrant collection: operaiq_memory
  - events
  - incidents
  - runbooks
  - services
  - audit_log
  - pattern_alerts
  - postmortems
        |
        v
OperaIQ API pattern watcher
        |
        v
POST /webhooks/qdrant-pattern
        |
        v
OperaIQ agent tools
  - search_similar_incidents
  - query_qdrant_memory
  - get_service_dependency_graph
  - get_runbook
  - execute_remediation
  - write_postmortem
        |
        v
Qdrant memory updated for the next incident
```

The UI is not a fake demo surface. The proof screen reads the project, log batch, pattern alert, incident, audit entries, and postmortem created by the Qdrant-backed flow.

---

## Tech stack

| Layer | Technology |
| --- | --- |
| Memory store | Qdrant vector database |
| Pattern detection | OperaIQ API watcher over Qdrant event payloads |
| Agent runtime | Node.js 20, TypeScript strict, Express |
| Agent memory tools | Local Qdrant memory package and MCP-style tool layer |
| Frontend | Next.js App Router, Tailwind CSS, live incident views |
| Auth | JWT, per-org webhook secrets |
| Generation | NVIDIA / Vertex / OpenAI-compatible provider support |
| Deployment | Render for web, AWS Docker Compose for API + private Qdrant |

---

## Quick test

Requirements: Docker, Node.js 20+, pnpm, and a real embedding provider key for the selected `EMBEDDING_PROVIDER`.

```bash
git clone https://github.com/Samfresh-ai/OperaIQ-Qdrant.git
cd OperaIQ-Qdrant
cp .env.example .env
pnpm install
docker compose -f docker-compose.qdrant.yml up -d
pnpm qdrant:setup-check
pnpm qdrant:seed
pnpm qdrant:verify
pnpm operaiq:test-tools
pnpm operaiq:quick-test
pnpm build
```

Local URLs:

- Web: `http://localhost:3000/test-app`
- API: `http://localhost:3001`
- Qdrant: `http://localhost:6333`

---

## Deployed verification

Open:

```text
https://operaiq.onrender.com/test-app
```

The final flow JSON should show:

```json
{
  "appLogsStored": true,
  "qdrantPatternMatched": true,
  "webhookFired": true,
  "operaiqActed": true,
  "operaiqVerified": true,
  "qdrantPostmortemStored": true
}
```

Proof artifacts are written under `artifacts/runtime/` and are not committed.
