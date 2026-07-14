"""Atomic, resumable, checksum-verifiable experiment execution."""

import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import polars as pl
import psutil  # type: ignore[import-untyped]
import yaml

from graphtrust.analysis.pipeline import analyze_bundle
from graphtrust.data import read_dataset
from graphtrust.data.checksums import (
    sha256_bytes,
    sha256_file,
    verify_checksum_file,
    write_checksum_file,
)
from graphtrust.experiments.metrics import evaluate_detection
from graphtrust.experiments.registry import ExperimentUnit
from graphtrust.schemas.findings import PathFinding
from graphtrust.schemas.manifests import RunManifest
from graphtrust.schemas.nodes import NodeType
from graphtrust.settings import ProjectConfig

RUN_FILES = (
    "run_manifest.json",
    "resolved_config.yaml",
    "environment.txt",
    "dataset_manifest.json",
    "predictions.parquet",
    "paths.parquet",
    "identity_scores.parquet",
    "remediation_plans.json",
    "metrics.json",
    "timings.json",
    "warnings.json",
    "stdout.log",
)


@dataclass(frozen=True, slots=True)
class ExperimentOutcome:
    run_id: str
    run_directory: Path
    status: str


def _json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _lock_checksum() -> str:
    path = Path("uv.lock")
    return sha256_file(path) if path.is_file() else "unavailable"


def _resolved_yaml(config: ProjectConfig) -> str:
    return yaml.safe_dump(config.model_dump(mode="json"), sort_keys=True, allow_unicode=True)


def deterministic_run_id(
    unit: ExperimentUnit, dataset_checksum: str, config_yaml: str, git_commit: str
) -> str:
    """Derive the run ID from exactly the preregistered provenance fields."""
    material = "\0".join(
        (dataset_checksum, sha256_bytes(config_yaml.encode()), git_commit, unit.method.value)
    )
    return "run-" + sha256_bytes(material.encode())[:24]


def verify_run_directory(path: Path) -> tuple[bool, tuple[str, ...]]:
    """Verify required files, checksum inventory, manifest, and manifest artifact hashes."""
    missing = tuple(
        name for name in (*RUN_FILES, "checksums.sha256") if not (path / name).is_file()
    )
    if missing:
        return False, tuple(f"missing:{name}" for name in missing)
    try:
        valid, failures = verify_checksum_file(path)
        manifest = RunManifest.model_validate_json(
            (path / "run_manifest.json").read_text(encoding="utf-8")
        )
        if manifest.completed_at is None:
            failures = (*failures, "manifest:not-complete")
        for name, digest in manifest.artifact_checksums.items():
            if not (path / name).is_file() or sha256_file(path / name) != digest:
                failures = (*failures, f"manifest-mismatch:{name}")
        return valid and not failures, failures
    except (OSError, ValueError) as error:
        return False, (f"invalid:{error}",)


def _finding_frames(findings: tuple[PathFinding, ...]) -> tuple[pl.DataFrame, pl.DataFrame]:
    predictions = pl.DataFrame(
        [
            {
                "finding_id": finding.finding_id,
                "method": finding.method.value,
                "source_identity_id": finding.source_identity_id,
                "target_asset_id": finding.target_asset_id,
                "path_risk": finding.risk.path_risk,
                "transition_cost": finding.risk.transition_cost,
                "path_length": len(finding.path),
                "search_complete": finding.search.search_complete,
                "caveats_json": json.dumps(finding.caveats),
            }
            for finding in findings
        ],
        schema={
            "finding_id": pl.String,
            "method": pl.String,
            "source_identity_id": pl.String,
            "target_asset_id": pl.String,
            "path_risk": pl.Float64,
            "transition_cost": pl.Float64,
            "path_length": pl.Int64,
            "search_complete": pl.Boolean,
            "caveats_json": pl.String,
        },
    )
    paths = pl.DataFrame(
        [
            {
                "finding_id": finding.finding_id,
                "position": step.position,
                "actor_before": step.actor_before,
                "actor_after": step.actor_after,
                "target_id": step.target_id,
                "capability": step.capability,
                "transition_type": step.transition_type,
                "condition_state": step.condition_state.value,
                "relative_exploitability": step.relative_exploitability,
                "raw_evidence_edge_ids_json": json.dumps(step.raw_evidence_edge_ids),
                "semantic_rule_id": step.semantic_rule_id,
            }
            for finding in findings
            for step in finding.path
        ],
        schema={
            "finding_id": pl.String,
            "position": pl.Int64,
            "actor_before": pl.String,
            "actor_after": pl.String,
            "target_id": pl.String,
            "capability": pl.String,
            "transition_type": pl.String,
            "condition_state": pl.String,
            "relative_exploitability": pl.Float64,
            "raw_evidence_edge_ids_json": pl.String,
            "semantic_rule_id": pl.String,
        },
    )
    return predictions, paths


def _environment() -> str:
    command = (
        ["uv", "pip", "freeze"] if shutil.which("uv") else [sys.executable, "-m", "pip", "freeze"]
    )
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    packages = result.stdout.strip() if result.returncode == 0 else "package inventory unavailable"
    return f"python={sys.version}\nplatform={platform.platform()}\n\n{packages}\n"


def _run_with_memory_sampling(
    bundle: Any,
    config: ProjectConfig,
    method: Any,
) -> tuple[Any, float, float]:
    """Run inference while sampling process resident memory."""
    try:
        candidate_process = psutil.Process()
        initial_rss = candidate_process.memory_info().rss
        process: psutil.Process | None = candidate_process
    except psutil.Error:
        # Some constrained containers hide the current PID from /proc.  The
        # process-wide high-water mark remains available through getrusage.
        process = None
        initial_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if platform.system() != "Darwin":
            initial_rss *= 1024
    peak_rss = [initial_rss]
    stop = threading.Event()

    def sample() -> None:
        while not stop.wait(0.05):
            if process is None:
                continue
            try:
                peak_rss[0] = max(peak_rss[0], process.memory_info().rss)
            except psutil.Error:
                return

    sampler = threading.Thread(target=sample, name="graphtrust-rss-sampler", daemon=True)
    sampler.start()
    started = time.perf_counter()
    try:
        analysis = analyze_bundle(bundle, config, (method,))
    finally:
        stop.set()
        sampler.join(timeout=1)
        if process is not None:
            with suppress(psutil.Error):
                peak_rss[0] = max(peak_rss[0], process.memory_info().rss)
    return analysis, time.perf_counter() - started, peak_rss[0] / (1024 * 1024)


def run_experiment_unit(
    unit: ExperimentUnit,
    config: ProjectConfig,
    *,
    output_root: Path = Path("artifacts/manifests"),
    resume: bool = False,
) -> ExperimentOutcome:
    """Execute one method without truth access, then score and atomically publish artifacts."""
    bundle = read_dataset(unit.dataset_path)
    dataset_checksum = bundle.tree_checksum or "unavailable"
    config_yaml = _resolved_yaml(config)
    commit = _git_commit()
    run_id = deterministic_run_id(unit, dataset_checksum, config_yaml, commit)
    destination = output_root / run_id
    if destination.exists():
        valid, _ = verify_run_directory(destination)
        if resume and valid:
            return ExperimentOutcome(run_id, destination, "skipped_verified")
        if valid:
            raise FileExistsError(f"Immutable run already exists: {destination}")
        corrupt = output_root / f".{run_id}.corrupt-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
        os.replace(destination, corrupt)

    output_root.mkdir(parents=True, exist_ok=True)
    staging = output_root / f".{run_id}.tmp-{uuid4().hex}"
    staging.mkdir()
    started = datetime.now(UTC)
    clock = time.perf_counter()
    try:
        analysis, inference_seconds, peak_rss_mib = _run_with_memory_sampling(
            bundle, config, unit.method
        )
        result = analysis.results[unit.method]
        # The benchmark truth is first accessed here, after all inference is complete.
        identity_count = sum(
            node.node_type
            in {
                NodeType.HUMAN_IDENTITY,
                NodeType.SERVICE_ACCOUNT,
                NodeType.WORKLOAD_IDENTITY,
                NodeType.EXTERNAL_IDENTITY,
            }
            for node in analysis.records.nodes
        )
        detection = evaluate_detection(
            result.findings,
            bundle.truth_paths,
            bundle.truth_scenarios,
            identity_count=identity_count,
        )
        predictions, paths = _finding_frames(result.findings)
        predictions.write_parquet(staging / "predictions.parquet", compression="zstd")
        paths.write_parquet(staging / "paths.parquet", compression="zstd")
        pl.DataFrame(
            [score.model_dump(mode="json") for score in result.identity_scores],
            schema={
                "node_id": pl.String,
                "critical_reach": pl.Float64,
                "best_path": pl.Float64,
                "path_diversity": pl.Float64,
                "blast_radius": pl.Float64,
                "control_weakness": pl.Float64,
                "ztri": pl.Float64,
            },
        ).write_parquet(staging / "identity_scores.parquet", compression="zstd")
        (staging / "resolved_config.yaml").write_text(config_yaml, encoding="utf-8", newline="\n")
        (staging / "environment.txt").write_text(_environment(), encoding="utf-8", newline="\n")
        _json(staging / "dataset_manifest.json", bundle.manifest.model_dump(mode="json"))
        _json(staging / "remediation_plans.json", [])
        explanation = {
            "raw_provenance_fraction": sum(
                bool(step.raw_evidence_edge_ids)
                for finding in result.findings
                for step in finding.path
            )
            / max(1, sum(len(finding.path) for finding in result.findings)),
            "score_decomposition_fraction": 1.0 if result.findings else 0.0,
            "search_status_fraction": 1.0,
        }
        _json(
            staging / "metrics.json",
            {
                "detection": detection.model_dump(mode="json"),
                "explanation_completeness": explanation,
            },
        )
        _json(
            staging / "timings.json",
            {
                "inference_seconds": inference_seconds,
                "total_seconds": time.perf_counter() - clock,
                "expanded_states": result.expanded_states,
                "candidate_paths_considered": result.candidate_paths_considered,
                "peak_rss_mib": peak_rss_mib,
            },
        )
        _json(staging / "warnings.json", list(result.warnings))
        (staging / "stdout.log").write_text(
            f"run_id={run_id}\ndataset_id={unit.dataset_id}\nmethod={unit.method.value}\nfindings={len(result.findings)}\n",
            encoding="utf-8",
            newline="\n",
        )
        artifact_names = tuple(name for name in RUN_FILES if name != "run_manifest.json")
        artifact_checksums = {name: sha256_file(staging / name) for name in artifact_names}
        completed = datetime.now(UTC)
        manifest = RunManifest(
            run_id=run_id,
            dataset_id=unit.dataset_id,
            dataset_checksum=dataset_checksum,
            resolved_config_checksum=sha256_bytes(config_yaml.encode()),
            git_commit=commit,
            method=unit.method,
            started_at=started,
            completed_at=completed,
            python_version=platform.python_version(),
            platform=platform.platform(),
            package_lock_sha256=_lock_checksum(),
            artifact_checksums=artifact_checksums,
            warnings=result.warnings,
        )
        _json(staging / "run_manifest.json", manifest.model_dump(mode="json"))
        write_checksum_file(staging, RUN_FILES)
        valid, failures = verify_run_directory(staging)
        if not valid:
            raise OSError(f"Run artifact verification failed: {failures}")
        os.replace(staging, destination)
        return ExperimentOutcome(run_id, destination, "completed")
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
