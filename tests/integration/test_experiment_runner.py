"""Immutable artifact execution and resumability integration tests."""

import json
from pathlib import Path

from graphtrust.data.io import write_dataset
from graphtrust.experiments.extended import run_extended_evaluation
from graphtrust.experiments.registry import ExperimentUnit
from graphtrust.experiments.reporting import generate_report
from graphtrust.experiments.runner import RUN_FILES, run_experiment_unit, verify_run_directory
from graphtrust.schemas.findings import AnalysisMethod
from graphtrust.schemas.manifests import DatasetVariant
from graphtrust.settings import load_project_config
from tests.integration.test_dataset_io import small_bundle


def test_experiment_run_is_complete_verified_and_resumable(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    written = write_dataset(small_bundle(), dataset)
    unit = ExperimentUnit(
        dataset_path=dataset,
        dataset_id=written.manifest.dataset_id,
        profile=written.manifest.profile,
        scale=written.manifest.scale.value,
        seed=written.manifest.generator_seed,
        variant=DatasetVariant.INJECTED_MIXED,
        method=AnalysisMethod.GRAPHTRUST,
    )
    runs = tmp_path / "runs"
    outcome = run_experiment_unit(unit, load_project_config(), output_root=runs)
    assert outcome.status == "completed"
    assert {path.name for path in outcome.run_directory.iterdir()} == {
        *RUN_FILES,
        "checksums.sha256",
    }
    assert verify_run_directory(outcome.run_directory) == (True, ())
    resumed = run_experiment_unit(
        unit,
        load_project_config(),
        output_root=runs,
        resume=True,
    )
    assert resumed.status == "skipped_verified"
    report = generate_report(runs, tmp_path / "paper")
    assert report["verified_run_ids"] == [outcome.run_id]
    assert json.loads((tmp_path / "paper" / "report.json").read_text())["rejected_runs"] == []


def test_extended_evaluation_runs_all_ablation_and_sensitivity_cases(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    write_dataset(small_bundle(), dataset)
    destination = run_extended_evaluation(
        dataset,
        load_project_config(),
        tmp_path / "extended",
    )
    ablations = json.loads((destination / "ablation_results.json").read_text())
    sensitivity = json.loads((destination / "sensitivity_results.json").read_text())
    assert len(ablations) == 7
    assert len(sensitivity["dirichlet_1000"]) == 1_000
    assert {row["parameter"] for row in sensitivity["one_at_a_time"]} >= {
        "maximum_depth",
        "criticality_threshold",
        "condition_mode",
        "top_k_per_source_target",
        "edge_exploitability_multiplier",
    }
    assert (destination / "checksums.sha256").is_file()
