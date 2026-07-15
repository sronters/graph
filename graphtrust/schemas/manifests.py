"""Immutable dataset and experiment manifest schemas."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, model_validator

from graphtrust.schemas.base import StrictModel
from graphtrust.schemas.findings import AnalysisMethod


class DatasetVariant(StrEnum):
    CLEAN = "clean"
    INJECTED_LOW = "injected_low"
    INJECTED_MIXED = "injected_mixed"
    REMEDIATED_TRUTH = "remediated_truth"


class DatasetScale(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class DatasetManifest(StrictModel):
    schema_version: str = "1.0"
    benchmark_name: str = "SEIB-2026"
    dataset_id: str
    profile: str
    scale: DatasetScale
    variant: DatasetVariant
    generator_seed: int
    generated_at: datetime
    git_commit: str
    config_sha256: str
    package_lock_sha256: str
    files: dict[str, str]
    realized_counts: dict[str, int]
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def generated_at_must_be_utc(self) -> "DatasetManifest":
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() != UTC.utcoffset(
            self.generated_at
        ):
            raise ValueError("generated_at must be timezone-aware UTC")
        return self


class RunManifest(StrictModel):
    schema_version: str = "1.0"
    run_id: str
    dataset_id: str
    dataset_checksum: str
    resolved_config_checksum: str
    git_commit: str
    method: AnalysisMethod
    started_at: datetime
    completed_at: datetime | None = None
    python_version: str
    platform: str
    package_lock_sha256: str
    artifact_checksums: dict[str, str] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()
