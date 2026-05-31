from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


Severity = Literal["sev1", "sev2", "sev3"]


class IncidentMemory(BaseModel):
    orgId: str = Field(min_length=2)
    incidentId: str = Field(min_length=3)
    service: str = Field(min_length=2)
    severity: Severity
    symptoms: list[str] = Field(min_length=1)
    rootCause: str = Field(min_length=8)
    resolution: str = Field(min_length=8)
    actionTaken: str = Field(min_length=3)
    resolved: bool
    createdAt: datetime


class SplunkAlert(BaseModel):
    orgId: str = Field(min_length=2)
    alertId: str = Field(min_length=3)
    service: str = Field(min_length=2)
    severity: Severity
    title: str = Field(min_length=4)
    message: str = Field(min_length=10)
    observedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    errorCount: int = Field(default=0, ge=0)
    p95LatencyMs: int = Field(default=0, ge=0)


class RecallMatch(BaseModel):
    incidentId: str
    service: str
    severity: Severity
    similarity: float
    similarityPercent: int
    rootCause: str
    resolution: str
    actionTaken: str
    symptoms: list[str]


class VerificationResult(BaseModel):
    action: str
    beforeErrorCount: int
    afterErrorCount: int
    signal: str
    verified: bool


class DemoResolution(BaseModel):
    alert: SplunkAlert
    match: RecallMatch
    recommendation: str
    verification: VerificationResult
    learnedIncident: IncidentMemory
    tenantPointCount: int
    narrative: str


class QdrantCollectionReport(BaseModel):
    collection: str
    mode: str
    exists: bool
    tenantPointCount: int | None = None
    indexedFields: list[str] = Field(default_factory=list)
    missingIndexes: list[str] = Field(default_factory=list)
    vectorSize: int | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app: str
    env: str
    qdrant: QdrantCollectionReport


class ReadinessResponse(BaseModel):
    ready: bool
    production: bool
    issues: list[str]
    warnings: list[str]
    qdrant: QdrantCollectionReport
