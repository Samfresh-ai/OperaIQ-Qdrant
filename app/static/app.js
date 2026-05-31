const statusEl = document.querySelector("#status");
const narrativeEl = document.querySelector("#narrative");
const similarityEl = document.querySelector("#similarity");
const actionEl = document.querySelector("#action");
const pointsEl = document.querySelector("#points");
const incidentEl = document.querySelector("#incident");
const verificationEl = document.querySelector("#verification");
const learnedEl = document.querySelector("#learned");
const quickRunButton = document.querySelector("#quick-run");
const resolveButton = document.querySelector("#resolve-alert");
const apiTokenInput = document.querySelector("#apiToken");

function alertPayload() {
  return {
    orgId: document.querySelector("#orgId").value,
    alertId: `manual-${Date.now()}`,
    service: document.querySelector("#service").value,
    severity: document.querySelector("#severity").value,
    title: document.querySelector("#title").value,
    message: document.querySelector("#message").value,
    errorCount: 327,
    p95LatencyMs: 5120,
  };
}

function renderResult(result) {
  statusEl.textContent = "resolved";
  narrativeEl.textContent = result.narrative;
  similarityEl.textContent = `${result.match.similarityPercent}%`;
  actionEl.textContent = result.recommendation;
  pointsEl.textContent = result.tenantPointCount;
  incidentEl.textContent = `${result.match.incidentId}: ${result.match.rootCause}`;
  verificationEl.textContent = result.verification.signal;
  learnedEl.textContent = `${result.learnedIncident.incidentId} written back to Qdrant for ${result.learnedIncident.orgId}.`;
}

function renderError(error) {
  statusEl.textContent = "error";
  narrativeEl.textContent = error.message || "Request failed.";
}

function authHeaders() {
  const token = apiTokenInput.value.trim();
  return token ? { Authorization: `Bearer ${token}` } : {};
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
    throw new Error(bodyText);
  }
  return response.json();
}

function setBusy(busy) {
  quickRunButton.disabled = busy;
  resolveButton.disabled = busy;
}

async function resolveCurrentAlert() {
  setBusy(true);
  statusEl.textContent = "embedding";
  narrativeEl.textContent = "Embedding alert and querying Qdrant with orgId filter...";

  try {
    await postJson("/api/seed?reset=false");
    renderResult(await postJson("/api/alerts/resolve", alertPayload()));
  } catch (error) {
    renderError(error);
  } finally {
    setBusy(false);
  }
}

async function runJudgeQuickRun() {
  setBusy(true);
  statusEl.textContent = "quick-run";
  narrativeEl.textContent = "Running the optional judge quick-run against seeded incident memory...";

  try {
    renderResult(await postJson("/api/judge/quick-run?reset=false"));
  } catch (error) {
    renderError(error);
  } finally {
    setBusy(false);
  }
}

quickRunButton.addEventListener("click", runJudgeQuickRun);
resolveButton.addEventListener("click", resolveCurrentAlert);

if (new URLSearchParams(window.location.search).get("autorun") === "1") {
  runJudgeQuickRun();
}
