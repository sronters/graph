"""Generate publication figures and traceable tables from verified artifacts."""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from graphtrust.experiments.reporting import load_run_rows

COLORS = ("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00")


def save_figure(figure: plt.Figure, output: Path, name: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    figure.savefig(output / f"{name}.svg", bbox_inches="tight")
    figure.savefig(output / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(figure)


def unavailable_figure(output: Path, name: str, title: str, reason: str) -> None:
    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.axis("off")
    axis.text(0.5, 0.58, title, ha="center", va="center", fontsize=16, weight="bold")
    axis.text(0.5, 0.42, reason, ha="center", va="center", fontsize=10, color="#555555")
    save_figure(figure, output, name)


def architecture_figure(output: Path) -> None:
    figure, axis = plt.subplots(figsize=(12, 4.8))
    axis.axis("off")
    labels = (
        "Canonical\nParquet",
        "Semantic\ncompiler",
        "Typed capability\ngraph",
        "Bounded path\nanalysis",
        "Verified\nremediation",
        "API + research\nartifacts",
    )
    for index, label in enumerate(labels):
        x = 0.02 + index * 0.165
        axis.add_patch(
            plt.Rectangle((x, 0.38), 0.135, 0.24, facecolor="#E5F1EF", edgecolor="#0F766E")
        )
        axis.text(x + 0.0675, 0.50, label, ha="center", va="center", fontsize=10)
        if index < len(labels) - 1:
            axis.annotate(
                "",
                (x + 0.16, 0.50),
                (x + 0.137, 0.50),
                arrowprops={"arrowstyle": "->", "color": "#555555"},
            )
    axis.text(0.5, 0.82, "GraphTrust system architecture", ha="center", fontsize=16, weight="bold")
    axis.text(
        0.5,
        0.16,
        "Truth is joined only after inference for evaluation; "
        "the browser cannot submit graph queries.",
        ha="center",
        fontsize=9,
    )
    save_figure(figure, output, "01_system_architecture")


def schema_figure(output: Path) -> None:
    figure, axis = plt.subplots(figsize=(10, 6))
    axis.axis("off")
    nodes = {
        "Human": (0.1, 0.75),
        "Group": (0.32, 0.75),
        "Role": (0.54, 0.75),
        "Service / workload": (0.1, 0.3),
        "Pipeline": (0.38, 0.3),
        "Critical asset": (0.72, 0.5),
    }
    for label, (x, y) in nodes.items():
        axis.add_patch(plt.Circle((x, y), 0.075, facecolor="#F4E4BE", edgecolor="#8A5A00"))
        axis.text(x, y, label, ha="center", va="center", fontsize=8)
    edges = (
        ("Human", "Group", "member of"),
        ("Group", "Role", "assigned role"),
        ("Role", "Critical asset", "capability"),
        ("Human", "Service / workload", "impersonates"),
        ("Service / workload", "Pipeline", "runs as"),
        ("Pipeline", "Critical asset", "deploys / writes"),
    )
    for source, target, label in edges:
        start, end = nodes[source], nodes[target]
        axis.annotate(
            label,
            end,
            start,
            ha="center",
            fontsize=7,
            arrowprops={"arrowstyle": "->", "color": "#0072B2"},
        )
    axis.text(
        0.5, 0.94, "Canonical heterogeneous graph schema", ha="center", fontsize=16, weight="bold"
    )
    save_figure(figure, output, "02_heterogeneous_schema")


def bootstrap_interval(values: np.ndarray) -> tuple[float, float]:
    if not len(values):
        return 0.0, 0.0
    rng = np.random.default_rng(104729)
    indexes = rng.integers(0, len(values), size=(10_000, len(values)))
    samples = values[indexes].mean(axis=1)
    return tuple(float(value) for value in np.quantile(samples, (0.025, 0.975)))


def bar_metric(
    rows: list[dict[str, Any]], output: Path, name: str, title: str, metrics: tuple[str, ...]
) -> None:
    if not rows:
        unavailable_figure(output, name, title, "No verified experiment runs are available.")
        return
    methods = sorted({str(row["method"]) for row in rows})
    x = np.arange(len(methods))
    figure, axis = plt.subplots(figsize=(9, 5))
    width = 0.8 / len(metrics)
    for metric_index, metric in enumerate(metrics):
        means: list[float] = []
        errors: list[list[float]] = [[], []]
        for method in methods:
            values = np.array([float(row[metric]) for row in rows if row["method"] == method])
            mean = float(values.mean())
            lower, upper = bootstrap_interval(values)
            means.append(mean)
            errors[0].append(mean - lower)
            errors[1].append(upper - mean)
        axis.bar(
            x + (metric_index - (len(metrics) - 1) / 2) * width,
            means,
            width,
            label=metric.replace("_", " "),
            color=COLORS[metric_index],
            yerr=np.array(errors),
            capsize=3,
        )
    axis.set_xticks(x, [method.replace("_", "\n") for method in methods])
    axis.set_ylim(0, 1.05)
    axis.set_ylabel("Metric value")
    axis.set_title(title)
    axis.legend(frameon=False)
    axis.grid(axis="y", alpha=0.2)
    save_figure(figure, output, name)


def example_path_figure(runs_root: Path, output: Path) -> None:
    for directory in sorted(path for path in runs_root.glob("run-*") if path.is_dir()):
        paths = pl.read_parquet(directory / "paths.parquet")
        if paths.is_empty():
            continue
        finding_id = str(paths[0, "finding_id"])
        selected = paths.filter(pl.col("finding_id") == finding_id).sort("position")
        figure, axis = plt.subplots(figsize=(12, 4.5))
        axis.axis("off")
        for index, row in enumerate(selected.iter_rows(named=True)):
            x = 0.05 + index * (0.9 / max(1, selected.height))
            axis.text(x, 0.66, str(row["actor_before"]), fontsize=8, ha="center", wrap=True)
            axis.annotate(
                str(row["transition_type"]),
                (x + 0.1, 0.5),
                (x, 0.5),
                fontsize=7,
                arrowprops={"arrowstyle": "->", "color": COLORS[index % len(COLORS)]},
            )
            axis.text(x + 0.1, 0.34, str(row["target_id"]), fontsize=8, ha="center", wrap=True)
        axis.text(
            0.5,
            0.92,
            "Explainable path with ordered semantic transitions",
            ha="center",
            fontsize=15,
            weight="bold",
        )
        axis.text(
            0.5, 0.08, f"Finding {finding_id} · run {directory.name}", ha="center", fontsize=8
        )
        save_figure(figure, output, "03_explainable_path")
        return
    unavailable_figure(
        output, "03_explainable_path", "Explainable path", "No verified run contains a ranked path."
    )


def remediation_figure(artifact_root: Path, output: Path, tables: Path) -> None:
    plans: list[dict[str, Any]] = []
    for path in artifact_root.rglob("remediation_plans.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, list):
            plans.extend({"source_artifact": str(path), **plan} for plan in value)
    csv_plans = [
        {
            key: (
                json.dumps(value, sort_keys=True, separators=(",", ":"))
                if isinstance(value, (list, dict))
                else value
            )
            for key, value in plan.items()
        }
        for plan in plans
    ]
    pl.DataFrame(csv_plans).write_csv(tables / "04_remediation_results.csv") if plans else (
        tables / "04_remediation_results.csv"
    ).write_text("source_artifact,plan_id,solver,target_fraction\n", encoding="utf-8")
    if not plans:
        unavailable_figure(
            output,
            "06_remediation_frontier",
            "Remediation cost versus exposure reduction",
            "No verified remediation plans are available.",
        )
        return
    figure, axis = plt.subplots(figsize=(8, 5))
    for solver, values in defaultdict(
        list,
        {
            solver: [plan for plan in plans if plan.get("solver") == solver]
            for solver in {plan.get("solver") for plan in plans}
        },
    ).items():
        axis.scatter(
            [float(plan["modeled_cost"]) for plan in values],
            [1 - float(plan["residual_exposure"]) for plan in values],
            label=solver,
        )
    axis.set_xlabel("Modeled business-removal cost")
    axis.set_ylabel("Exposure reduction")
    axis.set_title("Remediation cost versus exposure reduction")
    axis.legend(frameon=False)
    axis.grid(alpha=0.2)
    save_figure(figure, output, "06_remediation_frontier")


def runtime_and_ztri(runs_root: Path, output: Path, tables: Path) -> None:
    runtime_rows: list[dict[str, Any]] = []
    ztri: list[float] = []
    for directory in sorted(runs_root.glob("run-*")):
        if not directory.is_dir():
            continue
        manifest = json.loads((directory / "dataset_manifest.json").read_text(encoding="utf-8"))
        timing = json.loads((directory / "timings.json").read_text(encoding="utf-8"))
        runtime_rows.append(
            {
                "run_id": directory.name,
                "scale": manifest["scale"],
                "nodes": manifest["realized_counts"].get("nodes", 0),
                **timing,
            }
        )
        scores = pl.read_parquet(directory / "identity_scores.parquet")
        if "ztri" in scores.columns:
            ztri.extend(float(value) for value in scores["ztri"].to_list())
    if runtime_rows:
        pl.DataFrame(runtime_rows).write_csv(tables / "05_runtime_and_memory.csv")
        figure, axis = plt.subplots(figsize=(8, 5))
        axis.scatter(
            [row["nodes"] for row in runtime_rows],
            [row["inference_seconds"] for row in runtime_rows],
            c=COLORS[0],
        )
        axis.set_xscale("log")
        axis.set_yscale("log")
        axis.set_xlabel("Nodes")
        axis.set_ylabel("Inference seconds")
        axis.set_title("Runtime scaling (descriptive)")
        axis.grid(alpha=0.2)
        save_figure(figure, output, "07_runtime_memory_scaling")
    else:
        unavailable_figure(
            output,
            "07_runtime_memory_scaling",
            "Runtime and memory scaling",
            "No verified timing artifacts are available.",
        )
        (tables / "05_runtime_and_memory.csv").write_text(
            "run_id,scale,nodes,inference_seconds,peak_rss_mib\n", encoding="utf-8"
        )
    if ztri:
        figure, axis = plt.subplots(figsize=(8, 5))
        axis.hist(ztri, bins=20, color=COLORS[2], edgecolor="white")
        axis.set_xlabel("ZTRI")
        axis.set_ylabel("Identity count")
        axis.set_title("Identity risk-component distribution")
        save_figure(figure, output, "08_ztri_distribution")
    else:
        unavailable_figure(
            output,
            "08_ztri_distribution",
            "ZTRI distribution",
            "No verified identity-score artifacts are available.",
        )


def extended_figures(artifact_root: Path, output: Path, tables: Path) -> None:
    ablations: list[dict[str, Any]] = []
    sensitivity: list[dict[str, Any]] = []
    for path in artifact_root.glob("extended/extended-*/ablation_results.json"):
        ablations.extend(json.loads(path.read_text(encoding="utf-8")))
    for path in artifact_root.glob("extended/extended-*/sensitivity_results.json"):
        sensitivity.extend(json.loads(path.read_text(encoding="utf-8"))["one_at_a_time"])
    if ablations:
        table_rows = [
            {
                "name": row["name"],
                "scenario_f1": row["metrics"]["scenario_f1"],
                "exact_path_f1": row["metrics"]["exact_path_f1"],
            }
            for row in ablations
        ]
        pl.DataFrame(table_rows).write_csv(tables / "06_ablation_results.csv")
        figure, axis = plt.subplots(figsize=(9, 5))
        axis.barh(
            [row["name"].replace("_", " ") for row in table_rows],
            [row["scenario_f1"] for row in table_rows],
            color=COLORS[3],
        )
        axis.set_xlim(0, 1)
        axis.set_xlabel("Scenario F1")
        axis.set_title("GraphTrust ablation results")
        save_figure(figure, output, "09_ablation_results")
    else:
        unavailable_figure(
            output,
            "09_ablation_results",
            "Ablation results",
            "No verified extended-evaluation artifact is available.",
        )
        (tables / "06_ablation_results.csv").write_text(
            "name,scenario_f1,exact_path_f1\n", encoding="utf-8"
        )
    if sensitivity:
        figure, axis = plt.subplots(figsize=(9, 5))
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in sensitivity:
            groups[str(row["parameter"])].append(row)
        for index, (name, values) in enumerate(sorted(groups.items())):
            axis.scatter(
                [index] * len(values),
                [row["spearman"] for row in values],
                color=COLORS[index % len(COLORS)],
                label=name,
            )
        axis.set_xticks(
            range(len(groups)), [name.replace("_", "\n") for name in sorted(groups)], fontsize=7
        )
        axis.set_ylim(-1.05, 1.05)
        axis.set_ylabel("Spearman rank correlation")
        axis.set_title("Sensitivity and rank stability")
        axis.grid(axis="y", alpha=0.2)
        save_figure(figure, output, "10_sensitivity_rank_stability")
    else:
        unavailable_figure(
            output,
            "10_sensitivity_rank_stability",
            "Sensitivity and rank stability",
            "No verified extended-evaluation artifact is available.",
        )


def write_static_tables(tables: Path, rows: list[dict[str, Any]]) -> None:
    tables.mkdir(parents=True, exist_ok=True)
    datasets: dict[str, dict[str, Any]] = {}
    for row in rows:
        datasets.setdefault(
            str(row["dataset_id"]),
            {
                "dataset_id": row["dataset_id"],
                "profile": row["profile"],
                "scale": row["scale"],
                "variant": row["variant"],
                "seed": row["seed"],
                "source_run_ids": [],
            },
        )["source_run_ids"].append(row["run_id"])
    dataset_rows = [
        {**value, "source_run_ids": ";".join(sorted(value["source_run_ids"]))}
        for value in datasets.values()
    ]
    (
        pl.DataFrame(dataset_rows).write_csv(tables / "01_dataset_statistics.csv")
        if dataset_rows
        else (tables / "01_dataset_statistics.csv").write_text(
            "dataset_id,profile,scale,variant,seed,source_run_ids\n", encoding="utf-8"
        )
    )
    pl.DataFrame(
        [
            {"method": "B0 direct", "definition": "One-hop direct entitlements only"},
            {
                "method": "B1 privileged",
                "definition": "Typed traversal from privileged-labeled starts",
            },
            {"method": "B2 untyped", "definition": "Unit-cost traversal without semantic ranking"},
            {
                "method": "B3 native scope",
                "definition": "Direct, group, and native-scope relationships",
            },
            {"method": "GraphTrust", "definition": "Typed bounded whole-identity path ranking"},
        ]
    ).write_csv(tables / "02_baseline_definitions.csv")
    metric_columns = [
        "run_id",
        "dataset_id",
        "method",
        "exact_path_f1",
        "scenario_f1",
        "ndcg_at_10",
        "ndcg_at_20",
        "mean_reciprocal_rank",
    ]
    (
        pl.DataFrame(rows)
        .select(metric_columns)
        .write_csv(tables / "03_detection_ranking_metrics.csv")
        if rows
        else (tables / "03_detection_ranking_metrics.csv").write_text(
            ",".join(metric_columns) + "\n", encoding="utf-8"
        )
    )
    pl.DataFrame(
        [
            {
                "limitation": "Synthetic structural realism",
                "mitigation": "Three profiles, paired variants, explicit external-validity limits",
            },
            {
                "limitation": "Ordinal weights",
                "mitigation": "One-at-a-time and Dirichlet sensitivity",
            },
            {
                "limitation": "Static snapshot",
                "mitigation": "No claim about temporal sessions or successful misuse",
            },
            {
                "limitation": "Bounded top-K search",
                "mitigation": "Search completeness and truncation warnings persisted",
            },
            {
                "limitation": "Normalized provider semantics",
                "mitigation": "Named rules, raw provenance, and rejected-edge inventory",
            },
        ]
    ).write_csv(tables / "07_limitations_mitigations.csv")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, default=Path("artifacts/manifests"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/paper/figures"))
    arguments = parser.parse_args()
    rows, rejected = load_run_rows(arguments.runs) if arguments.runs.is_dir() else ([], [])
    if rejected:
        raise SystemExit("Rejected corrupt runs: " + "; ".join(rejected))
    tables = arguments.output.parent / "tables"
    write_static_tables(tables, rows)
    architecture_figure(arguments.output)
    schema_figure(arguments.output)
    example_path_figure(arguments.runs, arguments.output)
    bar_metric(
        rows,
        arguments.output,
        "04_detection_recall",
        "Detection recall comparison",
        ("exact_path_recall", "scenario_recall"),
    )
    bar_metric(
        rows,
        arguments.output,
        "05_ranking_quality",
        "Ranking quality comparison",
        ("ndcg_at_10", "ndcg_at_20"),
    )
    artifact_root = arguments.runs.parent
    remediation_figure(artifact_root, arguments.output, tables)
    runtime_and_ztri(arguments.runs, arguments.output, tables)
    extended_figures(artifact_root, arguments.output, tables)
    print(arguments.output)


if __name__ == "__main__":
    main()
