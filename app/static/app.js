const statusEl = document.querySelector("#status");
const narrativeEl = document.querySelector("#narrative");
const similarityEl = document.querySelector("#similarity");
const actionEl = document.querySelector("#action");
const pointsEl = document.querySelector("#points");
const incidentEl = document.querySelector("#incident");
const verificationEl = document.querySelector("#verification");
const learnedEl = document.querySelector("#learned");
const resolveButton = document.querySelector("#resolve-alert");
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
let seedPromise = null;
let memoryPrepared = false;

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

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderResult(result) {
  statusEl.textContent = "resolved";
  narrativeEl.textContent = result.narrative;
  similarityEl.textContent = `${result.match.similarityPercent}%`;
  actionEl.innerHTML = escapeHtml(result.recommendation).replaceAll("_", "_<wbr>");
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
}

function renderError(error) {
  statusEl.textContent = "error";
  narrativeEl.textContent = error.message || "Request failed.";
  writeDotEl.className = "status-dot";
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
  resolveButton.disabled = busy;
}

function renderReadiness(readiness) {
  const qdrant = readiness.qdrant || {};
  const indexes = qdrant.indexedFields || [];
  const missingIndexes = qdrant.missingIndexes || [];
  const warning = (readiness.warnings || [])[0] || "Live recall path";
  const warningSummary = warning.includes("local Qdrant mode")
    ? "local mode: index proof unavailable"
    : warning;

  qdrantModeEl.textContent = qdrant.mode || qdrantModeEl.textContent;
  pointCountEl.textContent = typeof qdrant.tenantPointCount === "number" ? qdrant.tenantPointCount : "--";
  topBrainCountEl.textContent = typeof qdrant.tenantPointCount === "number" ? qdrant.tenantPointCount : "--";
  indexSummaryEl.textContent = indexes.length ? `${indexes.length} payload indexes` : "no payload indexes reported";
  payloadIndexEvidenceEl.textContent = indexes.length ? indexes.join(", ") : "createdAt, orgId, resolved, service, severity";

  runtimeGateEl.classList.remove("blocked", "warn");
  if (!readiness.ready) {
    runtimeGateEl.classList.add("blocked");
  }

  runtimeStateEl.textContent = readiness.ready ? "Production ready" : readiness.issues?.[0] || "Production blocked";
  runtimeDetailEl.textContent = `${readiness.production ? "Production" : "Non-production"} · ${qdrant.mode || "Qdrant"} · ${warningSummary}`;

  qdrantDotEl.className = qdrant.exists === false ? "status-dot" : "status-dot live";
  indexDotEl.className = missingIndexes.length ? "status-dot warn" : "status-dot live";
  indexStateEl.textContent = missingIndexes.length ? `missing ${missingIndexes.join(", ")}` : "ready";
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

async function seedMemoryOnce() {
  if (!seedPromise) {
    statusEl.textContent = "preparing";
    narrativeEl.textContent =
      "Preparing baseline incident memory once. Resolve actions will not reset the collection.";
    seedPromise = postJson("/api/seed?reset=false")
      .then((seedResult) => {
        memoryPrepared = true;
        pointCountEl.textContent = seedResult.tenantPointCount;
        topBrainCountEl.textContent = seedResult.tenantPointCount;
        pointsEl.textContent = seedResult.tenantPointCount;
        statusEl.textContent = "waiting";
        narrativeEl.textContent =
          "App logs enter Qdrant, the watcher finds a pattern, OperaIQ acts, and the learned incident writes back.";
        return seedResult;
      })
      .catch((error) => {
        seedPromise = null;
        statusEl.textContent = "locked";
        narrativeEl.textContent =
          "Memory is not prepared yet. Use the local CLI or provide a production token before writing.";
        throw error;
      });
  }
  return seedPromise;
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

async function resolveCurrentAlert() {
  setBusy(true);
  statusEl.textContent = "embedding";
  narrativeEl.textContent = "Embedding alert and querying Qdrant with orgId filter...";

  try {
    if (!memoryPrepared) {
      await seedMemoryOnce();
    }
    renderResult(await postJson("/api/alerts/resolve", alertPayload()));
  } catch (error) {
    renderError(error);
  } finally {
    setBusy(false);
  }
}

resolveButton.addEventListener("click", resolveCurrentAlert);

prepareMemoryFromReadiness().catch(renderError);
