const statusEl = document.querySelector("#status");
const narrativeEl = document.querySelector("#narrative");
const similarityEl = document.querySelector("#similarity");
const actionEl = document.querySelector("#action");
const actionNarrativeEl = document.querySelector("#actionNarrative");
const pointsEl = document.querySelector("#points");
const incidentEl = document.querySelector("#incident");
const verificationEl = document.querySelector("#verification");
const learnedEl = document.querySelector("#learned");
const resolveButton = document.querySelector("#resolve-alert");
const generateWebhookButton = document.querySelector("#generate-webhook");
const copyWebhookButton = document.querySelector("#copy-webhook");
const apiTokenInput = document.querySelector("#apiToken");
const runtimeGateEl = document.querySelector(".runtime-gate");
const runtimeStateEl = document.querySelector("#runtimeState");
const runtimeDetailEl = document.querySelector("#runtimeDetail");
const qdrantModeEl = document.querySelector("#qdrantMode");
const pointCountEl = document.querySelector("#pointCount");
const topBrainCountEl = document.querySelector("#topBrainCount");
const topLastResolvedEl = document.querySelector("#topLastResolved");
const indexSummaryEl = document.querySelector("#indexSummary");
const qdrantDotEl = document.querySelector("#qdrantDot");
const indexDotEl = document.querySelector("#indexDot");
const writeDotEl = document.querySelector("#writeDot");
const tenantStateEl = document.querySelector("#tenantState");
const indexStateEl = document.querySelector("#indexState");
const writeStateEl = document.querySelector("#writeState");
const payloadIndexEvidenceEl = document.querySelector("#payloadIndexEvidence");
const webhookUrlEl = document.querySelector("#webhookUrl");
const webhookAuthEl = document.querySelector("#webhookAuth");
const webhookEventEl = document.querySelector("#webhookEvent");
const webhookPathEl = document.querySelector("#webhookPath");
const webhookResultEl = document.querySelector("#webhookResult");
const incidentTitleEl = document.querySelector("#incidentTitle");
const incidentStateEl = document.querySelector("#incidentState");
const incidentTimeEl = document.querySelector("#incidentTime");
const serviceCellEl = document.querySelector("#serviceCell");
const agentModeEl = document.querySelector("#agentMode");
const severityChipEl = document.querySelector("#severityChip");
let memoryPrepared = false;
let activeWebhookIntegration = null;
const expectedPayloadIndexes = "createdAt, kind, orgId, project, resolved, service, severity";

function alertPayload() {
  return {
    orgId: document.querySelector("#orgId").value,
    alertId: `operator-${Date.now()}`,
    service: document.querySelector("#service").value,
    severity: document.querySelector("#severity").value,
    title: document.querySelector("#title").value,
    message: document.querySelector("#message").value,
    errorCount: 327,
    p95LatencyMs: 5120,
  };
}

function integrationPayload() {
  return {
    orgId: document.querySelector("#orgId").value,
    project: document.querySelector("#project").value,
  };
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setIncidentState(state) {
  incidentStateEl.textContent = state;
  const className = state === "resolved" ? "resolved" : state === "failed" ? "failed" : "in-progress";
  incidentStateEl.className = `state-chip ${className}`;
  incidentTimeEl.textContent = "now";
}

function renderResult(result) {
  statusEl.textContent = "resolved";
  agentModeEl.textContent = "stored trace";
  narrativeEl.textContent = result.narrative;
  similarityEl.textContent = `${result.match.similarityPercent}%`;
  actionEl.innerHTML = escapeHtml(result.recommendation).replaceAll("_", "_<wbr>");
  actionNarrativeEl.textContent = result.recommendation;
  pointsEl.textContent = result.tenantPointCount;
  pointCountEl.textContent = result.tenantPointCount;
  topBrainCountEl.textContent = result.tenantPointCount;
  topLastResolvedEl.textContent = "now";
  incidentEl.textContent = `${result.match.incidentId}: ${result.match.rootCause}`;
  verificationEl.textContent = result.verification.signal;
  learnedEl.textContent = `${result.learnedIncident.incidentId} written back to Qdrant for ${result.learnedIncident.orgId}.`;
  tenantStateEl.textContent = "passed";
  writeStateEl.textContent = "written";
  writeDotEl.className = "status-dot live";
  incidentTitleEl.textContent = result.alert.title;
  serviceCellEl.textContent = result.alert.service;
  severityChipEl.textContent = result.alert.severity;
  webhookEventEl.textContent = `${result.alert.alertId} resolved by OperaIQ.`;
  setIncidentState("resolved");
}

function renderWebhookIntegration(integration) {
  activeWebhookIntegration = integration;
  webhookUrlEl.textContent = integration.webhookUrl;
  webhookAuthEl.textContent = `${integration.authMode} · ${integration.deliveryMethod}`;
  webhookPathEl.textContent = integration.webhookPath;
  webhookResultEl.textContent = "Webhook URL ready for the selected org/project.";
}

function formatEventTime(value) {
  if (!value) {
    return "unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "unknown";
  }
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function renderLatestIncident(activity) {
  if (!activity?.found || !activity.incident) {
    return;
  }

  const incident = activity.incident;
  statusEl.textContent = "resolved";
  agentModeEl.textContent = "qdrant memory";
  narrativeEl.textContent = `Latest resolved source event stored for ${incident.orgId}.`;
  actionEl.innerHTML = escapeHtml(incident.actionTaken).replaceAll("_", "_<wbr>");
  actionNarrativeEl.textContent = incident.actionTaken;
  similarityEl.textContent = "memory";
  incidentEl.textContent = `${incident.incidentId}: ${incident.rootCause}`;
  verificationEl.textContent = incident.resolution;
  learnedEl.textContent = `${incident.incidentId} is now available for the next matching event.`;
  pointsEl.textContent = activity.tenantPointCount ?? "--";
  pointCountEl.textContent = activity.tenantPointCount ?? "--";
  topBrainCountEl.textContent = activity.tenantPointCount ?? "--";
  topLastResolvedEl.textContent = formatEventTime(incident.createdAt);
  incidentTitleEl.textContent = incident.symptoms?.[0] || "Resolved source event";
  serviceCellEl.textContent = incident.service;
  severityChipEl.textContent = incident.severity;
  webhookEventEl.textContent = `${incident.incidentId} written back from source webhook flow.`;
  tenantStateEl.textContent = "passed";
  writeStateEl.textContent = "written";
  writeDotEl.className = "status-dot live";
  setIncidentState("resolved");
}

function renderTokenMissing() {
  statusEl.textContent = "token required";
  narrativeEl.textContent = "Paste the operator token before generating a webhook URL or using fallback resolve.";
  webhookResultEl.textContent = "Operator token required for this production write path.";
}

function renderError(error) {
  statusEl.textContent = "error";
  narrativeEl.textContent = error.message || "Request failed.";
  webhookResultEl.textContent = error.message || "Request failed.";
  writeDotEl.className = "status-dot";
  setIncidentState("failed");
}

function authHeaders() {
  const token = apiTokenInput.value.trim();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function hasOperatorToken() {
  return apiTokenInput.value.trim().length > 0;
}

async function postJson(url, body = null) {
  const headers = authHeaders();
  if (body) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(url, {
    method: "POST",
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const bodyText = await response.text();
    let message = bodyText;
    try {
      const parsed = JSON.parse(bodyText);
      message = parsed.detail || bodyText;
    } catch {
      message = bodyText;
    }
    throw new Error(message);
  }
  return response.json();
}

function setBusy(busy) {
  resolveButton.disabled = busy;
  generateWebhookButton.disabled = busy;
  copyWebhookButton.disabled = busy;
}

function renderReadiness(readiness) {
  const qdrant = readiness.qdrant || {};
  const indexes = qdrant.indexedFields || [];
  const missingIndexes = qdrant.missingIndexes || [];
  const localIndexProofUnavailable = qdrant.mode !== "server" && missingIndexes.length > 0;
  const warning = (readiness.warnings || [])[0] || "signed source intake";
  const warningSummary = warning.includes("local Qdrant mode")
    ? "local mode: index proof unavailable"
    : warning;

  qdrantModeEl.textContent = qdrant.mode || qdrantModeEl.textContent;
  pointCountEl.textContent = typeof qdrant.tenantPointCount === "number" ? qdrant.tenantPointCount : "--";
  topBrainCountEl.textContent = typeof qdrant.tenantPointCount === "number" ? qdrant.tenantPointCount : "--";
  indexSummaryEl.textContent = localIndexProofUnavailable
    ? "local index proof unavailable"
    : indexes.length
      ? `${indexes.length} payload indexes`
      : "no payload indexes reported";
  payloadIndexEvidenceEl.textContent = indexes.length ? indexes.join(", ") : expectedPayloadIndexes;

  runtimeGateEl.classList.remove("blocked", "warn");
  if (!readiness.ready) {
    runtimeGateEl.classList.add("blocked");
  } else if ((readiness.warnings || []).length) {
    runtimeGateEl.classList.add("warn");
  }

  runtimeStateEl.textContent = readiness.ready
    ? readiness.production
      ? "Production ready"
      : "Runtime ready"
    : readiness.issues?.[0] || "Production blocked";
  runtimeDetailEl.textContent = `${readiness.production ? "Production" : "Non-production"} · ${qdrant.mode || "Qdrant"} · ${warningSummary}`;

  qdrantDotEl.className = qdrant.exists === false ? "status-dot" : "status-dot live";
  indexDotEl.className = missingIndexes.length ? "status-dot warn" : "status-dot live";
  indexStateEl.textContent = localIndexProofUnavailable
    ? "local proof unavailable"
    : missingIndexes.length
      ? `missing ${missingIndexes.join(", ")}`
      : "ready";
}

async function loadReadiness() {
  try {
    const response = await fetch("/runtime/readiness", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`readiness failed with ${response.status}`);
    }
    const readiness = await response.json();
    renderReadiness(readiness);
    return readiness;
  } catch (error) {
    runtimeGateEl.classList.add("blocked");
    runtimeStateEl.textContent = error.message || "Readiness check failed";
    qdrantDotEl.className = "status-dot";
    indexDotEl.className = "status-dot";
    return null;
  }
}

async function prepareMemoryFromReadiness() {
  const readiness = await loadReadiness();
  const qdrant = readiness?.qdrant || {};
  if (qdrant.exists === false || qdrant.tenantPointCount === 0 || qdrant.tenantPointCount === null) {
    await postJson("/api/seed?reset=false");
    memoryPrepared = true;
    await loadReadiness();
    return;
  }
  memoryPrepared = true;
}

async function assertMemoryReady() {
  if (memoryPrepared) {
    return;
  }

  const readiness = await loadReadiness();
  const pointCount = readiness?.qdrant?.tenantPointCount;
  if (typeof pointCount === "number" && pointCount > 0) {
    memoryPrepared = true;
    return;
  }

  throw new Error("Memory is not prepared. Seed once from a trusted operator session.");
}

async function resolveCurrentAlert() {
  if (!hasOperatorToken()) {
    renderTokenMissing();
    return;
  }

  setBusy(true);
  statusEl.textContent = "embedding";
  agentModeEl.textContent = "agent active";
  setIncidentState("in_progress");
  narrativeEl.textContent = "Embedding alert and querying Qdrant with orgId filter.";

  try {
    await assertMemoryReady();
    renderResult(await postJson("/api/alerts/resolve", alertPayload()));
    await loadLatestIncident();
  } catch (error) {
    renderError(error);
  } finally {
    setBusy(false);
  }
}

function integrationMatchesForm(integration) {
  const current = integrationPayload();
  return integration?.orgId === current.orgId && integration?.project === current.project;
}

async function requestWebhookIntegration() {
  if (!hasOperatorToken()) {
    renderTokenMissing();
    return null;
  }

  const integration = await postJson("/api/integrations/webhook", integrationPayload());
  renderWebhookIntegration(integration);
  return integration;
}

async function generateWebhookIntegration() {
  if (!hasOperatorToken()) {
    renderTokenMissing();
    return null;
  }

  setBusy(true);
  statusEl.textContent = "registering";
  narrativeEl.textContent = "Registering a signed source webhook URL for this org and project.";
  webhookResultEl.textContent = "Generating webhook URL.";

  try {
    return await requestWebhookIntegration();
  } catch (error) {
    renderError(error);
    return null;
  } finally {
    setBusy(false);
  }
}

async function ensureWebhookIntegration() {
  if (integrationMatchesForm(activeWebhookIntegration)) {
    return activeWebhookIntegration;
  }
  return requestWebhookIntegration();
}

async function copyWebhookUrl() {
  if (!hasOperatorToken() && !integrationMatchesForm(activeWebhookIntegration)) {
    renderTokenMissing();
    return;
  }

  setBusy(true);
  try {
    const integration = await ensureWebhookIntegration();
    if (!integration) {
      return;
    }
    await navigator.clipboard.writeText(integration.webhookUrl);
    webhookResultEl.textContent = "Webhook URL copied.";
  } catch (error) {
    renderError(error);
  } finally {
    setBusy(false);
  }
}

async function loadLatestIncident() {
  const params = new URLSearchParams({ orgId: document.querySelector("#orgId").value });
  const response = await fetch(`/api/incidents/latest?${params.toString()}`, { cache: "no-store" });
  if (!response.ok) {
    return null;
  }
  const activity = await response.json();
  renderLatestIncident(activity);
  return activity;
}

resolveButton.addEventListener("click", resolveCurrentAlert);
generateWebhookButton.addEventListener("click", generateWebhookIntegration);
copyWebhookButton.addEventListener("click", copyWebhookUrl);

prepareMemoryFromReadiness()
  .then(() => loadLatestIncident())
  .catch(renderError);

setInterval(() => {
  loadLatestIncident().catch(() => null);
}, 8000);
