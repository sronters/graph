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

from graphtrust.data.checksums import sha256_file
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
REVIEW_METRICS = (
    "recall_at_5",
    "recall_at_10",
    "recall_at_20",
    "recall_at_50",
    "precision_at_5",
    "precision_at_10",
    "precision_at_20",
    "precision_at_50",
    "mean_reciprocal_rank",
)


def _cluster_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse paired variants before uncertainty estimation.

    The injected variants share one clean organization for each
    ``(profile, seed)``. Treating those variants as independent would
    overstate the effective sample size, so all summaries used for inference
    operate on one mean per enterprise graph.
    """
    grouped: dict[tuple[object, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["variant"] != "clean":
            grouped[(row["profile"], row["scale"], row["seed"], row["method"])].append(row)
    clustered: list[dict[str, Any]] = []
    for (profile, scale, seed, method), members in grouped.items():
        item: dict[str, Any] = {
            "profile": profile,
            "scale": scale,
            "seed": seed,
            "method": method,
            "variant": "cluster_mean",
        }
        for metric in (
            *PRIMARY_METRICS,
            "recall_at_5",
            "recall_at_10",
            "recall_at_20",
            "recall_at_50",
            "precision_at_5",
            "precision_at_10",
            "precision_at_20",
            "precision_at_50",
            "mean_reciprocal_rank",
        ):
            item[metric] = float(np.mean([float(member.get(metric, 0.0)) for member in members]))
        clustered.append(item)
    return clustered


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    clustered_rows = _cluster_rows(rows)
    scales = sorted({str(row["scale"]) for row in clustered_rows})
    for scale in scales:
        primary = [row for row in clustered_rows if row["scale"] == scale]
        for method in METHODS:
            selected = [row for row in primary if row["method"] == method]
            for metric in (*PRIMARY_METRICS, *REVIEW_METRICS):
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
                        "n_clusters": int(values.size),
                        "statistical_unit": "profile_seed_cluster",
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
        by_key: dict[tuple[object, ...], dict[str, list[dict[str, Any]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for row in primary:
            key = (row["profile"], row["seed"])
            by_key[key][str(row["method"])].append(row)
        complete = [
            methods for methods in by_key.values() if all(name in methods for name in METHODS)
        ]
        for metric in PRIMARY_METRICS:
            method_arrays = {
                method: np.asarray(
                    [
                        float(np.mean([member[metric] for member in group[method]]))
                        for group in complete
                    ],
                    dtype=float,
                )
                for method in METHODS
            }
            if len(complete) >= 2:
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
                    (
                        float(np.mean([member[metric] for member in group["graphtrust"]])),
                        float(np.mean([member[metric] for member in group[baseline]])),
                    )
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
                        "statistical_unit": "profile_seed_cluster",
                        "n_clusters": len(pairs),
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


def _evidence_manifest(runs: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Export one auditable row per verified immutable run."""
    by_id = {str(row["run_id"]): row for row in rows}
    manifest_rows: list[dict[str, Any]] = []
    for directory in sorted(path for path in runs.iterdir() if path.is_dir()):
        run_id = directory.name
        row = by_id.get(run_id)
        if row is None:
            continue
        run_manifest = json.loads((directory / "run_manifest.json").read_text(encoding="utf-8"))
        dataset_manifest = json.loads(
            (directory / "dataset_manifest.json").read_text(encoding="utf-8")
        )
        manifest_rows.append(
            {
                **{
                    key: row[key]
                    for key in (
                        "run_id",
                        "dataset_id",
                        "profile",
                        "scale",
                        "seed",
                        "variant",
                        "method",
                    )
                },
                "git_commit": run_manifest.get("git_commit", "unknown"),
                "dataset_checksum": run_manifest.get("dataset_checksum", "unknown"),
                "resolved_config_checksum": run_manifest.get(
                    "resolved_config_checksum", dataset_manifest.get("config_sha256", "unknown")
                ),
                "metrics_sha256": sha256_file(directory / "metrics.json"),
                "checksums_sha256": sha256_file(directory / "checksums.sha256"),
                "verification": "passed",
            }
        )
    return manifest_rows


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
            ("exact_path_recall", "ExactPathRecall"),
            ("ndcg_at_10", "NdcgTen"),
        ):
            row = next(
                (item for item in small if item["method"] == method and item["metric"] == metric),
                None,
            )
            if row:
                lines.append(_macro(f"{label}{short}", f"{row['mean']:.3f}"))
    for method in ("untyped", "native_scope", "graphtrust"):
        label = "".join(part.title() for part in method.split("_"))
        row = next(
            (
                item
                for item in payload["negative_controls"]
                if item.get("scale") == "small" and item.get("method") == method
            ),
            None,
        )
        if row:
            lines.append(
                _macro(f"{label}CleanBurden", f"{float(row['mean_unmatched_per_1000']):,.1f}")
            )
    for method, label in (("graphtrust", "Graphtrust"), ("untyped", "Untyped")):
        for budget in (5, 10, 20, 50):
            row = next(
                (
                    item
                    for item in small
                    if item["method"] == method and item["metric"] == f"recall_at_{budget}"
                ),
                None,
            )
            if row:
                lines.append(_macro(f"{label}RecallAt{budget}Budget", f"{row['mean']:.3f}"))
            row = next(
                (
                    item
                    for item in small
                    if item["method"] == method and item["metric"] == f"precision_at_{budget}"
                ),
                None,
            )
            if row:
                lines.append(_macro(f"{label}PrecisionAt{budget}Budget", f"{row['mean']:.3f}"))
        row = next(
            (
                item
                for item in small
                if item["method"] == method and item["metric"] == "mean_reciprocal_rank"
            ),
            None,
        )
        if row:
            lines.append(_macro(f"{label}Mrr", f"{row['mean']:.4f}"))
    plans = payload["remediation"]
    tests = payload["paired_tests"]
    for metric, metric_label in (
        ("risky_starting_identity_recall", "RiskyRecall"),
        ("exact_path_recall", "ExactPathRecall"),
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
        "statistical_unit": "profile_seed_cluster",
        "evidence_manifest": _evidence_manifest(runs, rows),
    }
    output.mkdir(parents=True, exist_ok=True)
    _json(output / "final_results.json", payload)
    pl.DataFrame(payload["summaries"]).write_csv(output / "final_metric_summary.csv")
    pl.DataFrame(payload["negative_controls"]).write_csv(output / "clean_negative_controls.csv")
    if payload["evidence_manifest"]:
        pl.DataFrame(payload["evidence_manifest"]).write_csv(output / "evidence_manifest.csv")
    else:
        (output / "evidence_manifest.csv").write_text(
            "run_id,dataset_id,profile,scale,seed,variant,method,git_commit,dataset_checksum,resolved_config_checksum,metrics_sha256,checksums_sha256,verification\n",
            encoding="utf-8",
        )
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
