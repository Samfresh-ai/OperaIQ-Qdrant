from functools import lru_cache

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.embedder import FastEmbedEmbedder
from app.memory_service import IncidentMemoryService
from app.models import DemoResolution, SplunkAlert
from app.seed import DEFAULT_ALERT, SEED_INCIDENTS


app = FastAPI(title="Sentinel Memory Layer", version="0.1.0")
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
            "collection": get_settings().qdrant_collection,
            "default_alert": DEFAULT_ALERT.model_dump(mode="json"),
        },
    )


@app.post("/api/seed")
def seed(reset: bool = True) -> dict[str, object]:
    service = get_memory_service()
    service.seed(SEED_INCIDENTS, reset=reset)
    return {
        "collection": service.collection,
        "seeded": len(SEED_INCIDENTS),
        "tenantPointCount": service.count_for_org(DEFAULT_ALERT.orgId),
    }


@app.post("/api/demo/run", response_model=DemoResolution)
def run_demo(reset: bool = True) -> DemoResolution:
    service = get_memory_service()
    service.seed(SEED_INCIDENTS, reset=reset)
    return service.resolve_alert(DEFAULT_ALERT)


@app.post("/api/alerts/resolve", response_model=DemoResolution)
def resolve_alert(alert: SplunkAlert) -> DemoResolution:
    service = get_memory_service()
    return service.resolve_alert(alert)

