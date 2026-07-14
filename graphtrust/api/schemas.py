"""Pydantic request and response contracts for the HTTP service."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from graphtrust.schemas.base import StrictModel
from graphtrust.schemas.findings import AnalysisMethod
from graphtrust.schemas.remediation import SolverName


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ErrorBody(StrictModel):
    code: str
    message: str


class ErrorResponse(StrictModel):
    error: ErrorBody


class HealthResponse(StrictModel):
    status: str
    version: str
    database: str


class DatasetSummary(StrictModel):
    dataset_id: str
    profile: str
    scale: str
    variant: str
    seed: int
    path: str
    counts: dict[str, int]
    warnings: tuple[str, ...] = ()


class DatasetPage(StrictModel):
    items: tuple[DatasetSummary, ...]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)


class AnalysisCreate(StrictModel):
    dataset_id: str = Field(min_length=1, max_length=300)
    methods: tuple[AnalysisMethod, ...] = Field(
        default=(AnalysisMethod.GRAPHTRUST,), min_length=1, max_length=5
    )


class AnalysisJob(StrictModel):
    analysis_id: str
    dataset_id: str
    methods: tuple[AnalysisMethod, ...]
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class RemediationCreate(StrictModel):
    solvers: tuple[SolverName, ...] = Field(
        default=(SolverName.CONSTRAINT_GENERATION,), min_length=1, max_length=4
    )
    targets: tuple[float, ...] = Field(default=(0.9,), min_length=1, max_length=3)


class CounterfactualRequest(StrictModel):
    removed_edge_ids: tuple[str, ...] = Field(min_length=1, max_length=1_000)


class ArtifactDescriptor(StrictModel):
    name: str
    size_bytes: int = Field(ge=0)
    sha256: str


class ArtifactPage(StrictModel):
    run_id: str
    artifacts: tuple[ArtifactDescriptor, ...]


class JsonPayload(StrictModel):
    data: dict[str, Any]
