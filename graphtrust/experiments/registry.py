"""Validated experiment registry expansion over available immutable datasets."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from graphtrust.data import read_dataset
from graphtrust.schemas.findings import AnalysisMethod
from graphtrust.schemas.manifests import DatasetVariant
from graphtrust.settings import load_yaml


class ExperimentRegistry(BaseModel):
    """Declared SEIB experiment matrix."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    benchmark: str
    profiles: tuple[str, ...] = Field(min_length=1)
    scales: tuple[str, ...] = Field(min_length=1)
    development_seeds: tuple[int, ...] = ()
    final_seeds: tuple[int, ...] = Field(min_length=1)
    variants: tuple[DatasetVariant, ...] = Field(min_length=1)
    methods: tuple[AnalysisMethod, ...] = Field(min_length=1)
    remediation_methods: tuple[str, ...] = ()
    large_profile_seed_count: int = Field(default=1, ge=1)


@dataclass(frozen=True, slots=True)
class ExperimentUnit:
    dataset_path: Path
    dataset_id: str
    profile: str
    scale: str
    seed: int
    variant: DatasetVariant
    method: AnalysisMethod


@dataclass(frozen=True, slots=True)
class RegistryExpansion:
    units: tuple[ExperimentUnit, ...]
    missing_datasets: tuple[str, ...]


def load_registry(path: Path) -> ExperimentRegistry:
    """Load and validate an experiment registry."""
    return ExperimentRegistry.model_validate(load_yaml(path))


def expand_registry(
    registry: ExperimentRegistry,
    *,
    data_root: Path = Path("data/generated"),
    include_development: bool = False,
) -> RegistryExpansion:
    """Expand the declared matrix, scheduling only checksum-valid available datasets."""
    seeds = (
        (*registry.final_seeds, *registry.development_seeds)
        if include_development
        else registry.final_seeds
    )
    units: list[ExperimentUnit] = []
    missing: list[str] = []
    for profile in registry.profiles:
        for scale in registry.scales:
            scale_seeds = seeds
            if scale == "large":
                scale_seeds = seeds[: registry.large_profile_seed_count]
            for seed in scale_seeds:
                for variant in registry.variants:
                    dataset_path = data_root / profile / scale / str(seed) / variant.value
                    if not dataset_path.is_dir():
                        missing.append(str(dataset_path))
                        continue
                    bundle = read_dataset(dataset_path)
                    for method in registry.methods:
                        units.append(
                            ExperimentUnit(
                                dataset_path=dataset_path,
                                dataset_id=bundle.manifest.dataset_id,
                                profile=profile,
                                scale=scale,
                                seed=seed,
                                variant=variant,
                                method=method,
                            )
                        )
    return RegistryExpansion(tuple(units), tuple(missing))


def registry_summary(registry: ExperimentRegistry) -> dict[str, Any]:
    """Return JSON-safe declared matrix metadata."""
    return registry.model_dump(mode="json")
