"""Run a frozen-seed depth-stratified stress test after truth-hidden inference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import polars as pl

from graphtrust.analysis.pipeline import analyze_bundle
from graphtrust.data import read_dataset
from graphtrust.schemas.findings import AnalysisMethod
from graphtrust.settings import load_project_config

METHODS = tuple(AnalysisMethod)


def _signature(finding: Any) -> tuple[str, str, tuple[str, ...]]:
    return (
        finding.source_identity_id,
        finding.target_asset_id,
        tuple(raw_id for step in finding.path for raw_id in step.raw_evidence_edge_ids),
    )


def _depth_records(bundle: Any, findings: tuple[Any, ...], *, depth: int) -> list[dict[str, Any]]:
    truth: dict[tuple[str, str, tuple[str, ...]], int] = {}
    for row in bundle.truth_paths.iter_rows(named=True):
        edges = tuple(str(value) for value in json.loads(str(row["edge_ids_json"])))
        truth[(str(row["source_id"]), str(row["target_id"]), edges)] = len(edges)
    predicted = {_signature(finding) for finding in findings}
    by_depth: dict[int, tuple[int, int]] = {}
    for signature, path_depth in truth.items():
        total, matched = by_depth.get(path_depth, (0, 0))
        by_depth[path_depth] = (total + 1, matched + int(signature in predicted))
    records: list[dict[str, Any]] = []
    for path_depth, (total, matched) in sorted(by_depth.items()):
        records.append(
            {
                "dataset_id": bundle.manifest.dataset_id,
                "profile": bundle.manifest.profile,
                "seed": bundle.manifest.generator_seed,
                "variant": bundle.manifest.variant,
                "analysis_depth": depth,
                "method": "",
                "path_depth": path_depth,
                "truth_paths": total,
                "matched_paths": matched,
                "recall": matched / total if total else 0.0,
            }
        )
    return records


def run(dataset_root: Path, config_path: Path, output: Path, depths: tuple[int, ...]) -> None:
    config = load_project_config(config_path)
    records: list[dict[str, Any]] = []
    datasets = sorted(
        path
        for path in dataset_root.rglob("injected_mixed")
        if path.is_dir() and (path / "manifest.json").is_file()
    )
    for dataset_path in datasets:
        bundle = read_dataset(dataset_path)
        for depth in depths:
            varied = config.model_copy(
                update={"analysis": config.analysis.model_copy(update={"maximum_depth": depth})}
            )
            results = analyze_bundle(bundle, varied, METHODS).results
            for method, result in results.items():
                for row in _depth_records(bundle, result.findings, depth=depth):
                    row["method"] = method.value
                    records.append(row)
    output.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(records).write_csv(output)
    print(json.dumps({"datasets": len(datasets), "rows": len(records), "output": str(output)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("data/generated"))
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--output", type=Path, default=Path("docs/evidence/depth_stress.csv"))
    parser.add_argument("--depths", default="1,2,3,4,5,6")
    args = parser.parse_args()
    depths = tuple(int(value) for value in args.depths.split(",") if value.strip())
    run(args.dataset_root, args.config, args.output, depths)


if __name__ == "__main__":
    main()
