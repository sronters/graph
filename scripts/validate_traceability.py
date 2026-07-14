"""Fail when reported artifacts cannot be traced to verified manifests."""

import argparse
import json
from pathlib import Path

from graphtrust.data.checksums import verify_checksum_file
from graphtrust.experiments.runner import verify_run_directory

FIGURES = (
    "01_system_architecture",
    "02_heterogeneous_schema",
    "03_explainable_path",
    "04_detection_recall",
    "05_ranking_quality",
    "06_remediation_frontier",
    "07_runtime_memory_scaling",
    "08_ztri_distribution",
    "09_ablation_results",
    "10_sensitivity_rank_stability",
    "11_profile_method_heatmap",
    "12_paired_differences",
    "13_attack_surface_atlas",
    "14_ztri_concentration",
)
TABLES = (
    "01_dataset_statistics.csv",
    "02_baseline_definitions.csv",
    "03_detection_ranking_metrics.csv",
    "04_remediation_results.csv",
    "05_runtime_and_memory.csv",
    "06_ablation_results.csv",
    "07_limitations_mitigations.csv",
)


def validate(artifacts: Path, *, allow_empty: bool = False) -> dict[str, object]:
    errors: list[str] = []
    runs_root = artifacts / "manifests"
    if not runs_root.is_dir() and (artifacts / "final_matrix").is_dir():
        runs_root = artifacts / "final_matrix"
    run_ids: set[str] = set()
    if runs_root.is_dir():
        for directory in sorted(path for path in runs_root.glob("run-*") if path.is_dir()):
            valid, failures = verify_run_directory(directory)
            if valid:
                run_ids.add(directory.name)
            else:
                errors.append(f"{directory.name}: {', '.join(failures)}")
    if not run_ids and not allow_empty:
        errors.append("no verified experiment runs")

    for directory in artifacts.glob("extended/extended-*"):
        valid, failures = verify_checksum_file(directory)
        if not valid:
            errors.append(f"{directory.name}: {', '.join(failures)}")

    paper_root = artifacts / "paper"
    if not paper_root.is_dir() and (artifacts / "final_paper").is_dir():
        paper_root = artifacts / "final_paper"
    report_path = paper_root / "generated" / "final_results.json"
    if not report_path.is_file():
        report_path = paper_root / "report.json"
    if not report_path.is_file() and (paper_root / "report" / "report.json").is_file():
        report_path = paper_root / "report" / "report.json"
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        referenced = set(report.get("verified_run_ids", []))
        missing = referenced.difference(run_ids)
        if missing:
            errors.append("report references unverified runs: " + ", ".join(sorted(missing)))
    elif not allow_empty:
        errors.append("paper report.json is missing")

    figures = paper_root / "figures"
    for name in FIGURES:
        for suffix in ("svg", "png"):
            if not (figures / f"{name}.{suffix}").is_file() and not allow_empty:
                errors.append(f"missing figure: {name}.{suffix}")
    tables = paper_root / "tables"
    for name in TABLES:
        if not (tables / name).is_file() and not allow_empty:
            errors.append(f"missing table: {name}")
    if errors:
        raise ValueError("Traceability validation failed: " + "; ".join(errors))
    return {
        "verified_run_ids": sorted(run_ids),
        "figure_count": len(FIGURES),
        "table_count": len(TABLES),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    parser.add_argument("--allow-empty", action="store_true")
    arguments = parser.parse_args()
    print(
        json.dumps(validate(arguments.artifacts, allow_empty=arguments.allow_empty), sort_keys=True)
    )


if __name__ == "__main__":
    main()
