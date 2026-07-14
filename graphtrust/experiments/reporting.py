"""Artifact-only experiment aggregation and traceable report generation."""

import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from graphtrust.experiments.runner import verify_run_directory
from graphtrust.experiments.statistics import paired_bootstrap_summary
from graphtrust.schemas.manifests import RunManifest


def load_run_rows(runs_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Load metrics only from verified immutable run directories."""
    rows: list[dict[str, Any]] = []
    rejected: list[str] = []
    for directory in sorted(
        path for path in runs_root.iterdir() if path.is_dir() and not path.name.startswith(".")
    ):
        valid, failures = verify_run_directory(directory)
        if not valid:
            rejected.append(f"{directory.name}: {', '.join(failures)}")
            continue
        manifest = RunManifest.model_validate_json(
            (directory / "run_manifest.json").read_text(encoding="utf-8")
        )
        dataset = json.loads((directory / "dataset_manifest.json").read_text(encoding="utf-8"))
        metrics = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))["detection"]
        rows.append(
            {
                "run_id": manifest.run_id,
                "dataset_id": manifest.dataset_id,
                "profile": dataset["profile"],
                "scale": dataset["scale"],
                "seed": dataset["generator_seed"],
                "variant": dataset["variant"],
                "method": manifest.method.value,
                **metrics,
            }
        )
    return rows, rejected


def generate_report(runs_root: Path, output: Path) -> dict[str, Any]:
    """Generate CSV, JSON, and Markdown tables with run IDs attached to every row."""
    rows, rejected = load_run_rows(runs_root)
    if not rows:
        raise ValueError("No verified experiment runs were found")
    output.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(rows)
    frame.write_csv(output / "per_dataset_metrics.csv")
    metric_names = ("exact_path_f1", "scenario_f1", "risky_starting_identity_recall", "ndcg_at_10")
    summaries: list[dict[str, Any]] = []
    for (method,), group in frame.group_by("method", maintain_order=True):
        for metric in metric_names:
            values = group[metric].to_numpy()
            summaries.append(
                {
                    "method": method,
                    "metric": metric,
                    "count": len(values),
                    "median": float(np.median(values)),
                    "q1": float(np.quantile(values, 0.25)),
                    "q3": float(np.quantile(values, 0.75)),
                    "mean": float(np.mean(values)),
                }
            )
    pl.DataFrame(summaries).write_csv(output / "aggregate_metrics.csv")
    paired: list[dict[str, Any]] = []
    by_key: dict[tuple[object, ...], dict[str, float]] = defaultdict(dict)
    for row in rows:
        key = (row["profile"], row["scale"], row["seed"], row["variant"])
        by_key[key][str(row["method"])] = float(row["scenario_f1"])
    for baseline in ("direct", "privileged", "untyped", "native_scope"):
        pairs = [
            (methods["graphtrust"], methods[baseline])
            for methods in by_key.values()
            if "graphtrust" in methods and baseline in methods
        ]
        if pairs:
            summary = paired_bootstrap_summary(
                np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs])
            )
            paired.append(
                {
                    "metric": "scenario_f1",
                    "treatment": "graphtrust",
                    "baseline": baseline,
                    **asdict(summary),
                }
            )
    payload: dict[str, Any] = {
        "verified_run_ids": sorted(str(row["run_id"]) for row in rows),
        "rejected_runs": rejected,
        "aggregate": summaries,
        "paired_comparisons": paired,
    }
    (output / "report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# GraphTrust experiment report",
        "",
        f"Verified immutable runs: {len(rows)}",
        "",
        "No claim in this report is computed outside the listed run artifacts.",
        "",
        "## Run IDs",
        "",
    ]
    lines.extend(f"- `{run_id}`" for run_id in payload["verified_run_ids"])
    lines.extend(
        [
            "",
            "## Aggregate table",
            "",
            "| Method | Metric | N | Median | IQR | Mean |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summaries:
        prefix = f"| {row['method']} | {row['metric']} | {row['count']} |"
        display_values = f" {row['median']:.4f} | {row['q1']:.4f}-{row['q3']:.4f} |"
        lines.append(f"{prefix}{display_values} {row['mean']:.4f} |")
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload
