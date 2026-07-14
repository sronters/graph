"""Build the final evidence matrix, statistical tests, and LaTeX result macros."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from graphtrust.experiments.reporting import load_run_rows
from graphtrust.experiments.statistics import (
    friedman_with_holm_wilcoxon,
    paired_bootstrap_summary,
)

METHODS = ("direct", "privileged", "untyped", "native_scope", "graphtrust")
PRIMARY_METRICS = (
    "risky_starting_identity_recall",
    "scenario_recall",
    "exact_path_recall",
    "ndcg_at_10",
)


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    scales = sorted({str(row["scale"]) for row in rows})
    for scale in scales:
        primary = [row for row in rows if row["scale"] == scale and row["variant"] != "clean"]
        for method in METHODS:
            selected = [row for row in primary if row["method"] == method]
            for metric in PRIMARY_METRICS:
                values = np.asarray([float(row[metric]) for row in selected], dtype=float)
                if not values.size:
                    continue
                rng = np.random.default_rng(104729)
                indexes = rng.integers(0, values.size, size=(10_000, values.size))
                boot = values[indexes].mean(axis=1)
                lower, upper = np.quantile(boot, (0.025, 0.975))
                summaries.append(
                    {
                        "scale": scale,
                        "method": method,
                        "metric": metric,
                        "n": int(values.size),
                        "mean": float(values.mean()),
                        "median": float(np.median(values)),
                        "ci95_low": float(lower),
                        "ci95_high": float(upper),
                    }
                )
    return summaries


def _paired(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    scales = sorted({str(row["scale"]) for row in rows})
    for scale in scales:
        primary = [row for row in rows if row["scale"] == scale and row["variant"] != "clean"]
        by_key: dict[tuple[object, ...], dict[str, dict[str, Any]]] = defaultdict(dict)
        for row in primary:
            key = (row["profile"], row["seed"], row["variant"])
            by_key[key][str(row["method"])] = row
        complete = [
            methods for methods in by_key.values() if all(name in methods for name in METHODS)
        ]
        for metric in PRIMARY_METRICS:
            method_arrays = {
                method: np.asarray(
                    [float(group[method][metric]) for group in complete], dtype=float
                )
                for method in METHODS
            }
            if complete:
                omnibus = friedman_with_holm_wilcoxon(method_arrays)
                comparisons.append(
                    {
                        "scale": scale,
                        "metric": metric,
                        "test": "friedman_holm_wilcoxon",
                        "n": len(complete),
                        **omnibus,
                    }
                )
            for baseline in METHODS[:-1]:
                pairs = [
                    (float(group["graphtrust"][metric]), float(group[baseline][metric]))
                    for group in complete
                ]
                if not pairs:
                    continue
                result = paired_bootstrap_summary(
                    np.asarray([pair[0] for pair in pairs]),
                    np.asarray([pair[1] for pair in pairs]),
                )
                comparisons.append(
                    {
                        "scale": scale,
                        "metric": metric,
                        "test": "paired_bootstrap",
                        "treatment": "graphtrust",
                        "baseline": baseline,
                        **asdict(result),
                    }
                )
    return comparisons


def _negative_controls(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for scale in sorted({str(row["scale"]) for row in rows}):
        for method in METHODS:
            selected = [
                float(row["unmatched_findings_per_1000_identities"])
                for row in rows
                if row["scale"] == scale and row["variant"] == "clean" and row["method"] == method
            ]
            if selected:
                values.append(
                    {
                        "scale": scale,
                        "method": method,
                        "n": len(selected),
                        "mean_unmatched_per_1000": float(np.mean(selected)),
                        "median_unmatched_per_1000": float(np.median(selected)),
                    }
                )
    return values


def _remediation(artifact_root: Path) -> list[dict[str, Any]]:
    plans: dict[str, dict[str, Any]] = {}
    for path in artifact_root.rglob("remediation_plans.json"):
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            continue
        for plan in loaded:
            plan_id = str(plan.get("plan_id", path))
            previous = plans.get(plan_id)
            if previous is None or (
                bool(plan.get("counterfactual_verified"))
                and not bool(previous.get("counterfactual_verified"))
            ):
                plans[plan_id] = {"source_artifact": str(path), **plan}
    return sorted(plans.values(), key=lambda plan: str(plan.get("solver")))


def _macro(name: str, value: str) -> str:
    return f"\\newcommand{{\\{name}}}{{{value}}}"


def _latex_macros(payload: dict[str, Any]) -> str:
    lines = ["% Generated from verified immutable run artifacts. Do not edit by hand."]
    completeness = payload["completeness"]
    lines.append(_macro("VerifiedRunCount", str(payload["verified_run_count"])))
    lines.append(_macro("SmallRunCount", str(completeness.get("small", {}).get("runs", 0))))
    lines.append(_macro("MediumRunCount", str(completeness.get("medium", {}).get("runs", 0))))
    small = [row for row in payload["summaries"] if row["scale"] == "small"]
    for method in METHODS:
        label = "".join(part.title() for part in method.split("_"))
        for metric, short in (
            ("risky_starting_identity_recall", "RiskyRecall"),
            ("scenario_recall", "ScenarioRecall"),
            ("ndcg_at_10", "NdcgTen"),
        ):
            row = next(
                (item for item in small if item["method"] == method and item["metric"] == metric),
                None,
            )
            if row:
                lines.append(_macro(f"{label}{short}", f"{row['mean']:.3f}"))
    plans = payload["remediation"]
    tests = payload["paired_tests"]
    for metric, metric_label in (
        ("risky_starting_identity_recall", "RiskyRecall"),
        ("ndcg_at_10", "NdcgTen"),
    ):
        for baseline, baseline_label in (("untyped", "Untyped"), ("native_scope", "Native")):
            row = next(
                (
                    item
                    for item in tests
                    if item.get("scale") == "small"
                    and item.get("metric") == metric
                    and item.get("test") == "paired_bootstrap"
                    and item.get("baseline") == baseline
                ),
                None,
            )
            if row:
                low, high = row["confidence_interval_95"]
                lines.extend(
                    [
                        _macro(
                            f"Vs{baseline_label}{metric_label}Difference",
                            f"{float(row['mean_difference']):+.3f}",
                        ),
                        _macro(
                            f"Vs{baseline_label}{metric_label}CI",
                            f"[{float(low):+.3f}, {float(high):+.3f}]",
                        ),
                    ]
                )
        omnibus = next(
            (
                item
                for item in tests
                if item.get("scale") == "small"
                and item.get("metric") == metric
                and item.get("test") == "friedman_holm_wilcoxon"
            ),
            None,
        )
        if omnibus:
            lines.append(
                _macro(f"Friedman{metric_label}P", f"{float(omnibus['friedman_p_value']):.3g}")
            )
    cut = next((plan for plan in plans if plan.get("solver") == "min_cut"), None)
    if cut:
        lines.extend(
            [
                _macro("CutChanges", str(len(cut.get("removed_edge_ids", [])))),
                _macro("CutCost", f"{float(cut['modeled_cost']):.2f}"),
                _macro("CutExposureReduction", f"{1 - float(cut['residual_exposure']):.3f}"),
                _macro("CutVerified", "yes" if cut.get("counterfactual_verified") else "no"),
            ]
        )
    return "\n".join(lines) + "\n"


def build(runs: Path, artifact_root: Path, output: Path) -> dict[str, Any]:
    rows, rejected = load_run_rows(runs)
    if rejected:
        raise ValueError("Corrupt runs rejected: " + "; ".join(rejected))
    completeness: dict[str, dict[str, int | bool]] = {}
    for scale in sorted({str(row["scale"]) for row in rows}):
        selected = [row for row in rows if row["scale"] == scale]
        expected = 3 * 5 * 3 * 5
        completeness[scale] = {
            "runs": len(selected),
            "expected_runs": expected,
            "complete": len(selected) == expected,
        }
    payload: dict[str, Any] = {
        "verified_run_count": len(rows),
        "verified_run_ids": sorted(str(row["run_id"]) for row in rows),
        "completeness": completeness,
        "summaries": _summaries(rows),
        "paired_tests": _paired(rows),
        "negative_controls": _negative_controls(rows),
        "remediation": _remediation(artifact_root),
    }
    output.mkdir(parents=True, exist_ok=True)
    _json(output / "final_results.json", payload)
    pl.DataFrame(payload["summaries"]).write_csv(output / "final_metric_summary.csv")
    pl.DataFrame(payload["negative_controls"]).write_csv(output / "clean_negative_controls.csv")
    (output / "results.tex").write_text(_latex_macros(payload), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, default=Path("artifacts/final_runs"))
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/final_paper/generated"))
    arguments = parser.parse_args()
    payload = build(arguments.runs, arguments.artifact_root, arguments.output)
    print(
        json.dumps(
            {"verified_runs": payload["verified_run_count"], "output": str(arguments.output)}
        )
    )


if __name__ == "__main__":
    main()
