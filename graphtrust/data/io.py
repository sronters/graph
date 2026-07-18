"""Atomic, truth-separated Parquet dataset I/O."""

import json
import os
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from uuid import uuid4

import polars as pl

from graphtrust.data.checksums import (
    combined_checksum,
    file_checksums,
    read_checksum_file,
    verify_checksum_file,
    write_checksum_file,
)
from graphtrust.data.dataset_card import render_dataset_card
from graphtrust.schemas.manifests import DatasetManifest

PARQUET_FILES = (
    "nodes.parquet",
    "edges.parquet",
    "conditions.parquet",
    "activity.parquet",
    "assets.parquet",
    "truth_paths.parquet",
    "truth_scenarios.parquet",
    "protected_requirements.parquet",
)
METADATA_FILES = ("manifest.json", "dataset_card.md", "quality_report.json")
REQUIRED_FILES = (*PARQUET_FILES, *METADATA_FILES, "checksums.sha256")


@dataclass(frozen=True, slots=True)
class DatasetBundle:
    """In-memory representation of one canonical dataset directory."""

    nodes: pl.DataFrame
    edges: pl.DataFrame
    conditions: pl.DataFrame
    activity: pl.DataFrame
    assets: pl.DataFrame
    truth_paths: pl.DataFrame
    truth_scenarios: pl.DataFrame
    protected_requirements: pl.DataFrame
    manifest: DatasetManifest
    quality_report: dict[str, object]
    dataset_card: str | None = None
    tree_checksum: str | None = None

    def frames(self) -> dict[str, pl.DataFrame]:
        """Return canonical filename-to-frame mapping."""
        return {
            "nodes.parquet": self.nodes,
            "edges.parquet": self.edges,
            "conditions.parquet": self.conditions,
            "activity.parquet": self.activity,
            "assets.parquet": self.assets,
            "truth_paths.parquet": self.truth_paths,
            "truth_scenarios.parquet": self.truth_scenarios,
            "protected_requirements.parquet": self.protected_requirements,
        }


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_staging(bundle: DatasetBundle, staging: Path) -> DatasetBundle:
    staging.mkdir(parents=True, exist_ok=False)
    for filename, frame in bundle.frames().items():
        frame.write_parquet(staging / filename, compression="zstd", statistics=True)

    parquet_checksums = file_checksums(staging, PARQUET_FILES)
    manifest = bundle.manifest.model_copy(update={"files": parquet_checksums})
    _write_json(staging / "manifest.json", manifest.model_dump(mode="json"))

    dataset_card = bundle.dataset_card or render_dataset_card(manifest)
    (staging / "dataset_card.md").write_text(dataset_card, encoding="utf-8", newline="\n")
    _write_json(staging / "quality_report.json", bundle.quality_report)
    inventory = write_checksum_file(staging, (*PARQUET_FILES, *METADATA_FILES))
    return replace(
        bundle,
        manifest=manifest,
        dataset_card=dataset_card,
        tree_checksum=combined_checksum(inventory),
    )


def write_dataset(bundle: DatasetBundle, destination: Path) -> DatasetBundle:
    """Validate and atomically write a new immutable dataset directory."""
    from graphtrust.data.validation import validate_bundle

    report = validate_bundle(bundle)
    if not report.valid:
        raise ValueError("Dataset validation failed: " + "; ".join(report.errors))
    if destination.exists():
        raise FileExistsError(f"Dataset destination already exists: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{destination.name}.tmp-{uuid4().hex}"
    try:
        written = _write_staging(bundle, staging)
        verified, failures = verify_checksum_file(staging)
        if not verified:
            raise OSError(f"Staging checksum verification failed: {failures}")
        os.replace(staging, destination)
        return written
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def read_dataset(
    source: Path,
    *,
    verify_checksums: bool = True,
    skip_frames: frozenset[str] = frozenset(),
) -> DatasetBundle:
    """Read a complete dataset and optionally verify its immutable inventory.

    ``skip_frames`` names Parquet files (e.g. ``"activity.parquet"``) whose
    contents the caller will not use; they are returned as empty frames
    instead of being parsed, avoiding the peak-RAM cost of materializing
    large Parquet files the caller immediately discards. Checksum
    verification (file bytes, not decoded frames) is unaffected.
    """
    missing = [filename for filename in REQUIRED_FILES if not (source / filename).is_file()]
    if missing:
        raise FileNotFoundError(f"Dataset is incomplete; missing: {', '.join(missing)}")
    if verify_checksums:
        verified, failures = verify_checksum_file(source)
        if not verified:
            raise ValueError("Dataset checksum verification failed: " + ", ".join(failures))

    frames = {
        filename: (
            pl.DataFrame() if filename in skip_frames else pl.read_parquet(source / filename)
        )
        for filename in PARQUET_FILES
    }
    manifest = DatasetManifest.model_validate_json(
        (source / "manifest.json").read_text(encoding="utf-8")
    )
    inventory = read_checksum_file(source / "checksums.sha256")
    return DatasetBundle(
        nodes=frames["nodes.parquet"],
        edges=frames["edges.parquet"],
        conditions=frames["conditions.parquet"],
        activity=frames["activity.parquet"],
        assets=frames["assets.parquet"],
        truth_paths=frames["truth_paths.parquet"],
        truth_scenarios=frames["truth_scenarios.parquet"],
        protected_requirements=frames["protected_requirements.parquet"],
        manifest=manifest,
        quality_report=json.loads((source / "quality_report.json").read_text(encoding="utf-8")),
        dataset_card=(source / "dataset_card.md").read_text(encoding="utf-8"),
        tree_checksum=combined_checksum(inventory),
    )
