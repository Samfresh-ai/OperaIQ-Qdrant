# OperaIQ Render Deployment

Render hosts the OperaIQ web app. The API and Qdrant run separately on AWS through `deploy/aws/operaiq-compose.yml`.

## Current Shape

- `operaiq`: Render Docker web service from `apps/web/Dockerfile`
- API target: `https://operaiq-api.3.208.71.125.sslip.io`
- Qdrant target: private container on the AWS host, reached only by the API

`render.yaml` sets `NEXT_PUBLIC_API_URL` to the public API URL. The browser never connects to Qdrant directly.

## Required Render Variables

```text
NEXT_PUBLIC_API_URL=https://<operaiq-api-url>
NEXT_PUBLIC_QDRANT_DASHBOARD_URL=
```

## Required API Variables

These live on the AWS API host, not in the Render web service:

```text
NODE_ENV=production
OPERAIQ_RUNTIME_ENV=production
AGENT_NAME=OperaIQ
OPERAIQ_REMEDIATION_BACKEND=admin-endpoint
OPERAIQ_GENERATION_PROVIDER=nvidia
NVIDIA_API_KEY=<secret>
JWT_SECRET=<secret>
WEBHOOK_SECRET=<secret>
AGENT_TOOL_SECRET=<secret>
PUBLIC_APP_URL=https://<operaiq-web-url>
API_PUBLIC_URL=https://<operaiq-api-url>
NEXT_PUBLIC_API_URL=https://<operaiq-api-url>
AGENT_TOOL_EXECUTION_BASE_URL=https://<operaiq-api-url>
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=<secret>
QDRANT_COLLECTION=operaiq_memory
EMBEDDING_PROVIDER=nvidia
```

## Readiness

Before submission:

1. `GET https://<operaiq-api-url>/health` returns `status: ok`.
2. `GET https://<operaiq-api-url>/runtime/readiness` returns `mode: autonomous-ready`.
3. `https://<operaiq-web-url>/test-app` completes the six proof stages:

```text
app logs stored -> Qdrant pattern matched -> webhook fired -> OperaIQ acted -> OperaIQ verified -> Qdrant postmortem stored
```
