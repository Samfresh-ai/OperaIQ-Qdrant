from functools import lru_cache

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.embedder import FastEmbedEmbedder
from app.memory_service import IncidentMemoryService
from app.models import DemoResolution, HealthResponse, ReadinessResponse, SplunkAlert
from app.seed import DEFAULT_ALERT, SEED_INCIDENTS


app = FastAPI(title="OperaIQ", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@lru_cache
def get_memory_service() -> IncidentMemoryService:
    settings = get_settings()
    return IncidentMemoryService(
        settings=settings,
        embedder=FastEmbedEmbedder(settings.embedding_model),
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "app_name": get_settings().app_name,
            "collection": get_settings().qdrant_collection,
            "qdrant_mode": get_settings().qdrant_mode,
            "default_alert": DEFAULT_ALERT.model_dump(mode="json"),
        },
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    report = get_memory_service().collection_report(org_id=DEFAULT_ALERT.orgId)
    indexed_enough = report.mode != "server" or not report.missingIndexes
    return HealthResponse(
        status="ok" if report.exists and indexed_enough else "degraded",
        app=settings.app_name,
        env=settings.app_env,
        qdrant=report,
    )


@app.get("/runtime/readiness", response_model=ReadinessResponse)
def readiness() -> ReadinessResponse:
    settings = get_settings()
    report = get_memory_service().collection_report(org_id=DEFAULT_ALERT.orgId)
    issues = settings.production_issues()
    warnings: list[str] = []

    if not report.exists:
        issues.append(f"Qdrant collection {report.collection} has not been created")
    if report.missingIndexes and report.mode == "server":
        issues.append("missing payload indexes: " + ", ".join(report.missingIndexes))
    if report.missingIndexes and report.mode != "server":
        warnings.append("local Qdrant mode does not expose active payload index proof")
    if report.mode == "local-path":
        warnings.append("local Qdrant path is persistent but not a multi-process production server")

    return ReadinessResponse(
        ready=len(issues) == 0,
        production=settings.is_production,
        issues=issues,
        warnings=warnings,
        qdrant=report,
    )


@app.post("/api/seed")
def seed(reset: bool = True) -> dict[str, object]:
    if reset and not get_settings().allow_demo_reset:
        raise HTTPException(status_code=403, detail="demo reset is disabled")

    service = get_memory_service()
    try:
        service.seed(SEED_INCIDENTS, reset=reset)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "collection": service.collection,
        "seeded": len(SEED_INCIDENTS),
        "tenantPointCount": service.count_for_org(DEFAULT_ALERT.orgId),
    }


@app.post("/api/demo/run", response_model=DemoResolution)
def run_demo(reset: bool = True) -> DemoResolution:
    if reset and not get_settings().allow_demo_reset:
        raise HTTPException(status_code=403, detail="demo reset is disabled")

    service = get_memory_service()
    try:
        service.seed(SEED_INCIDENTS, reset=reset)
        return service.resolve_alert(DEFAULT_ALERT)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/alerts/resolve", response_model=DemoResolution)
def resolve_alert(alert: SplunkAlert) -> DemoResolution:
    service = get_memory_service()
    try:
        return service.resolve_alert(alert)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
