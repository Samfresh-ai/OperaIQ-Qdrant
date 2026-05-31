const statusEl = document.querySelector("#status");
const narrativeEl = document.querySelector("#narrative");
const similarityEl = document.querySelector("#similarity");
const actionEl = document.querySelector("#action");
const pointsEl = document.querySelector("#points");
const incidentEl = document.querySelector("#incident");
const verificationEl = document.querySelector("#verification");
const learnedEl = document.querySelector("#learned");
const runButton = document.querySelector("#run-demo");

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
  narrativeEl.textContent = error.message || "Demo failed.";
}

async function runDemo() {
  runButton.disabled = true;
  statusEl.textContent = "embedding";
  narrativeEl.textContent = "Embedding alert and querying Qdrant with orgId filter...";

  try {
    await fetch("/api/seed?reset=true", { method: "POST" });
    const response = await fetch("/api/alerts/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(alertPayload()),
    });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(body);
    }
    renderResult(await response.json());
  } catch (error) {
    renderError(error);
  } finally {
    runButton.disabled = false;
  }
}

runButton.addEventListener("click", runDemo);

if (new URLSearchParams(window.location.search).get("autorun") === "1") {
  runDemo();
}
