"""Application settings and deterministic YAML configuration loading."""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnalysisSettings(BaseModel):
    """Bounded graph-analysis settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    maximum_depth: int = Field(default=8, ge=1, le=32)
    top_k_per_source_target: int = Field(default=20, ge=1)
    top_k_per_source: int = Field(default=100, ge=1)
    global_path_cap: int = Field(default=250_000, ge=1)
    criticality_threshold: float = Field(default=0.70, ge=0, le=1)
    include_dormant: bool = False
    include_disabled: bool = False


class StorageSettings(BaseModel):
    """Repository-relative storage paths."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    data_root: Path = Path("data")
    artifact_root: Path = Path("artifacts")
    database_path: Path = Path("artifacts/graphtrust.duckdb")


class RuntimeSettings(BaseModel):
    """Execution behavior shared by CLI and service."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workers: int | Literal["auto"] = "auto"
    deterministic: bool = True
    json_logs: bool = False


class ProjectConfig(BaseModel):
    """Resolved GraphTrust configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    backend: Literal["networkx", "igraph"] = "networkx"
    condition_mode: Literal["conservative", "strict"] = "conservative"
    analysis: AnalysisSettings = AnalysisSettings()
    storage: StorageSettings = StorageSettings()
    runtime: RuntimeSettings = RuntimeSettings()


class EnvironmentSettings(BaseSettings):
    """Environment-only overrides for service process paths and logging."""

    model_config = SettingsConfigDict(
        env_prefix="GRAPHTRUST_",
        env_file=".env",
        extra="ignore",
    )

    data_root: Path = Path("data")
    artifact_root: Path = Path("artifacts")
    database_path: Path = Path("artifacts/graphtrust.duckdb")
    log_level: str = "INFO"
    json_logs: bool = False


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a mapping from YAML and reject empty or non-mapping documents."""
    with path.open("r", encoding="utf-8") as stream:
        value = yaml.safe_load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"Configuration {path} must contain a YAML mapping")
    return value


def load_project_config(path: Path = Path("configs/default.yaml")) -> ProjectConfig:
    """Validate a project configuration file."""
    return ProjectConfig.model_validate(load_yaml(path))
