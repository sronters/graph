"""Generate publication figures and traceable tables from verified artifacts."""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import polars as pl
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch

from graphtrust.experiments.reporting import load_run_rows

COLORS = ("#2563EB", "#F59E0B", "#10B981", "#A855F7", "#06B6D4", "#EF4444")
INK = "#172033"
MUTED = "#64748B"
PAPER = "#F8FAFC"
METHOD_ORDER = ("direct", "privileged", "untyped", "native_scope", "graphtrust")
METHOD_LABELS = {
    "direct": "Direct",
    "privileged": "Privileged-only",
    "untyped": "Untyped graph",
    "native_scope": "Native scope",
    "graphtrust": "GraphTrust",
}
METHOD_COLORS = dict(zip(METHOD_ORDER, COLORS, strict=False))

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 15,
        "axes.titleweight": "bold",
        "axes.labelcolor": INK,
        "axes.edgecolor": "#CBD5E1",
        "axes.linewidth": 0.8,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "text.color": INK,
        "figure.facecolor": PAPER,
        "axes.facecolor": PAPER,
        "savefig.facecolor": PAPER,
    }
)


def save_figure(figure: Figure, output: Path, name: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    figure.text(0.995, 0.008, "GraphTrust · SEIB-2026", ha="right", fontsize=6.5, color="#94A3B8")
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
    figure, axis = plt.subplots(figsize=(13, 5.2))
    axis.axis("off")
    labels = (
        ("01", "Raw IAM evidence", "Parquet + provenance"),
        ("02", "Semantic compiler", "provider-aware rules"),
        ("03", "Capability graph", "typed + conditional"),
        ("04", "Path analytics", "bounded and ranked"),
        ("05", "Remediation", "cut + counterfactual"),
        ("06", "Evidence package", "API · tables · figures"),
    )
    for index, (number, label, detail) in enumerate(labels):
        x = 0.018 + index * 0.164
        color = COLORS[index % len(COLORS)]
        axis.add_patch(
            FancyBboxPatch(
                (x, 0.34),
                0.14,
                0.31,
                boxstyle="round,pad=0.012,rounding_size=0.025",
                facecolor="white",
                edgecolor="#E2E8F0",
                linewidth=1.2,
            )
        )
        axis.add_patch(
            FancyBboxPatch(
                (x + 0.012, 0.565),
                0.036,
                0.056,
                boxstyle="round,pad=0.004,rounding_size=0.01",
                facecolor=color,
                edgecolor=color,
            )
        )
        axis.text(
            x + 0.030,
            0.592,
            number,
            color="white",
            weight="bold",
            ha="center",
            va="center",
            fontsize=8,
        )
        axis.text(x + 0.07, 0.49, label, ha="center", va="center", fontsize=10, weight="bold")
        axis.text(x + 0.07, 0.405, detail, ha="center", va="center", fontsize=7.5, color=MUTED)
        if index < len(labels) - 1:
            axis.add_patch(
                FancyArrowPatch(
                    (x + 0.142, 0.5),
                    (x + 0.166, 0.5),
                    arrowstyle="-|>",
                    mutation_scale=12,
                    linewidth=1.1,
                    color="#94A3B8",
                )
            )
    axis.text(
        0.5,
        0.86,
        "From raw entitlements to verified recommendations",
        ha="center",
        fontsize=18,
        weight="bold",
    )
    axis.text(
        0.5,
        0.16,
        "Truth is joined only after inference for evaluation; "
        "the browser cannot submit graph queries.",
        ha="center",
        fontsize=9.5,
        color=MUTED,
    )
    save_figure(figure, output, "01_system_architecture")


def schema_figure(output: Path) -> None:
    figure, axis = plt.subplots(figsize=(10, 6))
    axis.axis("off")
    nodes = {
        "Human": (0.10, 0.72, COLORS[0]),
        "Group": (0.32, 0.78, COLORS[4]),
        "Role": (0.55, 0.72, COLORS[3]),
        "Service\nidentity": (0.15, 0.28, COLORS[2]),
        "CI/CD\npipeline": (0.42, 0.25, COLORS[1]),
        "Critical\nasset": (0.78, 0.50, COLORS[5]),
    }
    for label, (x, y, color) in nodes.items():
        axis.add_patch(
            Circle((x, y), 0.078, facecolor=color, edgecolor="white", linewidth=2.2, alpha=0.94)
        )
        axis.text(x, y, label, ha="center", va="center", fontsize=8.5, color="white", weight="bold")
    edges = (
        ("Human", "Group", "member of"),
        ("Group", "Role", "assigned role"),
        ("Role", "Critical\nasset", "capability"),
        ("Human", "Service\nidentity", "impersonates"),
        ("Service\nidentity", "CI/CD\npipeline", "runs as"),
        ("CI/CD\npipeline", "Critical\nasset", "deploys / writes"),
    )
    for source, target, label in edges:
        start, end = nodes[source][:2], nodes[target][:2]
        axis.annotate(
            label,
            end,
            start,
            ha="center",
            fontsize=7,
            arrowprops={
                "arrowstyle": "-|>",
                "color": "#64748B",
                "lw": 1.2,
                "connectionstyle": "arc3,rad=0.08",
            },
        )
    axis.text(
        0.5,
        0.94,
        "Two hidden routes to one critical asset",
        ha="center",
        fontsize=17,
        weight="bold",
    )
    axis.text(
        0.5,
        0.08,
        "Every effective transition retains the raw IAM evidence "
        "and semantic rule that produced it.",
        ha="center",
        fontsize=9,
        color=MUTED,
    )
    save_figure(figure, output, "02_heterogeneous_schema")


def bootstrap_interval(values: np.ndarray) -> tuple[float, float]:
    if not len(values):
        return 0.0, 0.0
    rng = np.random.default_rng(104729)
    indexes = rng.integers(0, len(values), size=(10_000, len(values)))
    samples = values[indexes].mean(axis=1)
    quantiles = np.quantile(samples, (0.025, 0.975))
    return float(quantiles[0]), float(quantiles[1])


def bar_metric(
    rows: list[dict[str, Any]], output: Path, name: str, title: str, metrics: tuple[str, ...]
) -> None:
    if not rows:
        unavailable_figure(output, name, title, "No verified experiment runs are available.")
        return
    methods = [method for method in METHOD_ORDER if any(row["method"] == method for row in rows)]
    y = np.arange(len(methods))
    figure, axis = plt.subplots(figsize=(10, 5.6))
    for metric_index, metric in enumerate(metrics):
        means: list[float] = []
        lowers: list[float] = []
        uppers: list[float] = []
        for method in methods:
            values = np.array([float(row[metric]) for row in rows if row["method"] == method])
            mean = float(values.mean())
            lower, upper = bootstrap_interval(values)
            means.append(mean)
            lowers.append(lower)
            uppers.append(upper)
        offset = (metric_index - (len(metrics) - 1) / 2) * 0.18
        axis.errorbar(
            means,
            y + offset,
            xerr=np.array(
                [
                    [mean - lower for mean, lower in zip(means, lowers, strict=True)],
                    [u - m for m, u in zip(means, uppers, strict=True)],
                ]
            ),
            fmt="o",
            markersize=8,
            linewidth=2,
            capsize=4,
            label=metric.replace("_", " ").title(),
            color=COLORS[metric_index],
            markeredgecolor="white",
            markeredgewidth=1,
        )
    axis.set_yticks(y, [METHOD_LABELS[m] for m in methods])
    axis.set_xlim(-0.02, 1.02)
    axis.set_xlabel("Mean across paired enterprise graphs · 95% bootstrap CI")
    axis.set_title(title)
    axis.legend(frameon=False)
    axis.grid(axis="x", alpha=0.22)
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.invert_yaxis()
    save_figure(figure, output, name)


def review_budget_figure(rows: list[dict[str, Any]], output: Path, tables: Path) -> None:
    """Show the operational review queue rather than only exhaustive recall."""
    selected = [row for row in rows if row.get("variant") != "clean"]
    audit_path = Path("docs/evidence/review_budget_summary.csv")
    audit_frame = pl.read_csv(audit_path) if audit_path.is_file() else pl.DataFrame()
    audit_mode = not selected or "precision_at_50" not in selected[0]
    if audit_mode and audit_frame.is_empty():
        unavailable_figure(
            output,
            "15_review_budget_curve",
            "Analyst review budget",
            "No verified review-budget metrics are available.",
        )
        return
    budgets = (5, 10, 20, 50)
    records: list[dict[str, Any]] = []
    figure, axes = plt.subplots(1, 2, figsize=(12, 5.2), sharex=True)
    for method in METHOD_ORDER:
        if audit_mode:
            method_rows = audit_frame.filter(pl.col("method") == method).sort("review_budget")
            if method_rows.is_empty():
                continue
            budgets_for_method = [int(value) for value in method_rows["review_budget"].to_list()]
            recalls = [float(value) for value in method_rows["recall"].to_list()]
            precisions = [
                float(value) if value is not None else np.nan
                for value in method_rows["precision"].to_list()
            ]
            n_runs = 0
        else:
            method_rows = [row for row in selected if row["method"] == method]
            if not method_rows:
                continue
            budgets_for_method = list(budgets)
            recalls = [
                float(np.mean([row[f"recall_at_{budget}"] for row in method_rows]))
                for budget in budgets
            ]
            precisions = [
                float(np.mean([row[f"precision_at_{budget}"] for row in method_rows]))
                for budget in budgets
            ]
            n_runs = len(method_rows)
        for budget, recall, precision in zip(budgets_for_method, recalls, precisions, strict=True):
            records.append(
                {
                    "method": method,
                    "review_budget": budget,
                    "recall": recall,
                    "precision": precision,
                    "n_runs": n_runs,
                }
            )
        color = METHOD_COLORS[method]
        axes[0].plot(
            budgets_for_method,
            np.asarray(recalls) * 100,
            marker="o",
            lw=2.6,
            color=color,
            label=METHOD_LABELS[method],
        )
        axes[1].plot(
            budgets_for_method,
            np.asarray(precisions) * 100,
            marker="o",
            lw=2.6,
            color=color,
            label=METHOD_LABELS[method],
        )
    pl.DataFrame(records).write_csv(tables / "08_review_budget_metrics.csv")
    axes[0].set_title("Recall surfaced within the queue")
    axes[0].set_ylabel("Exact-path recall (%)")
    axes[1].set_title("Evidence density in the queue")
    axes[1].set_ylabel("Exact-path precision (%)")
    for axis in axes:
        axis.set_xlabel("Findings an analyst can review (K)")
        axis.set_xticks(budgets)
        axis.grid(alpha=0.2)
        axis.spines[["top", "right"]].set_visible(False)
    axes[1].legend(frameon=False, fontsize=8)
    figure.suptitle(
        "GraphTrust converts reachability into a reviewable queue", weight="bold", fontsize=15
    )
    save_figure(figure, output, "15_review_budget_curve")


def depth_stratified_figure(runs_root: Path, output: Path, tables: Path) -> None:
    """Measure exact-path recall by planted path depth without using truth at inference."""
    records: list[dict[str, Any]] = []
    dataset_by_id: dict[str, Path] = {}
    for manifest_path in Path("data/generated").rglob("dataset_manifest.json"):
        try:
            dataset_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        dataset_by_id[str(dataset_manifest.get("dataset_id"))] = manifest_path.parent
    for directory in sorted(path for path in runs_root.glob("run-*") if path.is_dir()):
        dataset = json.loads((directory / "dataset_manifest.json").read_text(encoding="utf-8"))
        if dataset.get("variant") == "clean":
            continue
        dataset_path = dataset_by_id.get(str(dataset.get("dataset_id")))
        if dataset_path is None:
            continue
        truth = pl.read_parquet(dataset_path / "truth_paths.parquet")
        paths = pl.read_parquet(directory / "paths.parquet")
        truth_by_signature: dict[tuple[str, str, tuple[str, ...]], int] = {}
        for row in truth.iter_rows(named=True):
            edges = tuple(str(value) for value in json.loads(str(row["edge_ids_json"])))
            truth_by_signature[(str(row["source_id"]), str(row["target_id"]), edges)] = len(edges)
        prediction_signatures: set[tuple[str, str, tuple[str, ...]]] = set()
        for _finding_id, group in paths.group_by("finding_id", maintain_order=True):
            rows = group.sort("position").iter_rows(named=True)
            rows = list(rows)
            if not rows:
                continue
            prediction_signatures.add(
                (
                    str(rows[0]["actor_before"]),
                    str(rows[-1]["target_id"]),
                    tuple(
                        raw_id
                        for item in rows
                        for raw_id in json.loads(str(item["raw_evidence_edge_ids_json"]))
                    ),
                )
            )
        by_depth: dict[int, tuple[int, int]] = {}
        for signature, depth in truth_by_signature.items():
            total, matched = by_depth.get(depth, (0, 0))
            by_depth[depth] = (total + 1, matched + int(signature in prediction_signatures))
        for depth, (total, matched) in by_depth.items():
            records.append(
                {
                    "run_id": directory.name,
                    "profile": dataset["profile"],
                    "seed": dataset["generator_seed"],
                    "method": json.loads(
                        (directory / "run_manifest.json").read_text(encoding="utf-8")
                    )["method"],
                    "path_depth": depth,
                    "truth_paths": total,
                    "matched_paths": matched,
                    "recall": matched / total if total else 0.0,
                }
            )
    if not records:
        unavailable_figure(
            output,
            "16_recall_by_path_depth",
            "Recall by path depth",
            "No truth-separated depth artifacts are available.",
        )
        return
    frame = pl.DataFrame(records)
    frame.write_csv(tables / "09_recall_by_path_depth.csv")
    aggregate = frame.group_by(["method", "path_depth"]).agg(
        pl.col("recall").mean().alias("recall")
    )
    figure, axis = plt.subplots(figsize=(9.6, 5.6))
    for method in METHOD_ORDER:
        selected = aggregate.filter(pl.col("method") == method).sort("path_depth")
        if selected.is_empty():
            continue
        axis.plot(
            selected["path_depth"],
            selected["recall"] * 100,
            marker="o",
            lw=2.6,
            color=METHOD_COLORS[method],
            label=METHOD_LABELS[method],
        )
    axis.set_xlabel("Planted path depth (raw IAM transitions)")
    axis.set_ylabel("Exact-path recall (%)")
    axis.set_title("Whole-graph methods gain as privilege paths become multi-hop")
    axis.set_xticks(sorted(frame["path_depth"].unique().to_list()))
    axis.grid(alpha=0.2)
    axis.legend(frameon=False, ncols=2)
    axis.spines[["top", "right"]].set_visible(False)
    save_figure(figure, output, "16_recall_by_path_depth")


def example_path_figure(runs_root: Path, output: Path) -> None:
    candidates: list[tuple[float, Path, str]] = []
    for directory in sorted(path for path in runs_root.glob("run-*") if path.is_dir()):
        predictions = pl.read_parquet(directory / "predictions.parquet")
        if predictions.is_empty() or predictions[0, "method"] != "graphtrust":
            continue
        multi_hop = predictions.filter(pl.col("path_length") >= 3)
        ranked = multi_hop if not multi_hop.is_empty() else predictions
        top = ranked.sort("path_risk", descending=True).row(0, named=True)
        candidates.append((float(top["path_risk"]), directory, str(top["finding_id"])))
    for risk, directory, finding_id in sorted(candidates, reverse=True):
        paths = pl.read_parquet(directory / "paths.parquet")
        selected = paths.filter(pl.col("finding_id") == finding_id).sort("position")
        if selected.is_empty():
            continue
        steps = selected.to_dicts()
        node_ids = [str(steps[0]["actor_before"])] + [str(row["target_id"]) for row in steps]
        figure, axis = plt.subplots(figsize=(13, 5.8))
        axis.axis("off")
        xs = np.linspace(0.08, 0.92, len(node_ids))
        for index, (x, node_id) in enumerate(zip(xs, node_ids, strict=True)):
            color = COLORS[5] if index == len(node_ids) - 1 else COLORS[index % 5]
            axis.add_patch(Circle((x, 0.5), 0.052, color=color, ec="white", lw=2.5, zorder=3))
            role = (
                "CRITICAL ASSET"
                if index == len(node_ids) - 1
                else ("START IDENTITY" if index == 0 else f"HOP {index}")
            )
            axis.text(x, 0.59, role, ha="center", fontsize=7, color=color, weight="bold")
            short = node_id if len(node_id) <= 24 else node_id[:11] + "…" + node_id[-10:]
            axis.text(x, 0.39, short, ha="center", va="top", fontsize=7.3, color=INK)
        for index, row in enumerate(steps):
            left, right = xs[index], xs[index + 1]
            axis.add_patch(
                FancyArrowPatch(
                    (left + 0.053, 0.5),
                    (right - 0.053, 0.5),
                    arrowstyle="-|>",
                    mutation_scale=16,
                    linewidth=3.2,
                    color="#334155",
                    zorder=2,
                )
            )
            transition = str(row["transition_type"]).replace("_", " ")
            axis.text(
                (left + right) / 2,
                0.535,
                transition,
                ha="center",
                fontsize=7.2,
                weight="bold",
                color="#334155",
            )
            axis.text(
                (left + right) / 2,
                0.455,
                f"exploitability {float(row['relative_exploitability']):.2f}",
                ha="center",
                fontsize=6.8,
                color=MUTED,
            )
        axis.text(
            0.5,
            0.91,
            "Highest-ranked hidden privilege path",
            ha="center",
            fontsize=18,
            weight="bold",
        )
        axis.text(
            0.5,
            0.82,
            f"Relative path risk {risk:.3f} · every hop maps back to raw IAM evidence",
            ha="center",
            fontsize=10,
            color=MUTED,
        )
        axis.text(
            0.5,
            0.10,
            f"Finding {finding_id} · immutable run {directory.name}",
            ha="center",
            fontsize=7.5,
            color="#94A3B8",
        )
        save_figure(figure, output, "03_explainable_path")
        return
    unavailable_figure(
        output, "03_explainable_path", "Explainable path", "No verified run contains a ranked path."
    )


def attack_surface_atlas(runs_root: Path, output: Path) -> None:
    """Render the union of high-ranked multi-hop paths from one verified run."""
    candidates: list[tuple[float, Path]] = []
    for directory in sorted(path for path in runs_root.glob("run-*") if path.is_dir()):
        predictions = pl.read_parquet(directory / "predictions.parquet")
        if predictions.is_empty() or predictions[0, "method"] != "graphtrust":
            continue
        multi_hop = predictions.filter(pl.col("path_length") >= 3)
        if not multi_hop.is_empty():
            maximum_risk = multi_hop["path_risk"].max()
            candidates.append(
                (float(cast(float, maximum_risk)) if maximum_risk is not None else 0.0, directory)
            )
    if not candidates:
        unavailable_figure(
            output,
            "13_attack_surface_atlas",
            "Identity attack-surface atlas",
            "No verified multi-hop GraphTrust paths are available.",
        )
        return

    _, directory = max(candidates)
    predictions = (
        pl.read_parquet(directory / "predictions.parquet")
        .filter(pl.col("path_length") >= 3)
        .sort("path_risk", descending=True)
        .head(18)
    )
    finding_ids = predictions["finding_id"].to_list()
    paths = pl.read_parquet(directory / "paths.parquet").filter(
        pl.col("finding_id").is_in(finding_ids)
    )
    graph: nx.DiGraph[str] = nx.DiGraph()
    top_id = str(finding_ids[0])
    top_edges: set[tuple[str, str]] = set()
    for row in paths.sort(("finding_id", "position")).iter_rows(named=True):
        source, target = str(row["actor_before"]), str(row["target_id"])
        graph.add_edge(source, target)
        if str(row["finding_id"]) == top_id:
            top_edges.add((source, target))

    position = nx.spring_layout(graph, seed=104729, k=1.35 / np.sqrt(max(1, len(graph))))
    figure, axis = plt.subplots(figsize=(13, 8.2))
    axis.axis("off")
    ordinary = [edge for edge in graph.edges if edge not in top_edges]
    nx.draw_networkx_edges(
        graph,
        position,
        edgelist=ordinary,
        edge_color="#94A3B8",
        alpha=0.28,
        width=1,
        arrowsize=10,
        connectionstyle="arc3,rad=0.06",
        ax=axis,
    )
    nx.draw_networkx_edges(
        graph,
        position,
        edgelist=list(top_edges),
        edge_color=COLORS[5],
        alpha=0.95,
        width=3,
        arrowsize=17,
        connectionstyle="arc3,rad=0.04",
        ax=axis,
    )
    type_colors = {
        "human": COLORS[0],
        "service": COLORS[2],
        "workload": COLORS[4],
        "role": COLORS[3],
        "group": COLORS[1],
        "application": "#0EA5E9",
        "pipeline": "#F97316",
        "secret": COLORS[5],
        "resource": "#475569",
    }
    node_colors = [
        type_colors.get(node.split(":", 1)[0], type_colors["resource"]) for node in graph.nodes
    ]
    node_sizes = [160 + 95 * graph.degree(node) for node in graph.nodes]
    nx.draw_networkx_nodes(
        graph,
        position,
        node_color=node_colors,
        node_size=node_sizes,
        edgecolors="white",
        linewidths=1.2,
        alpha=0.96,
        ax=axis,
    )
    highlighted = {node for edge in top_edges for node in edge}
    labels = {
        node: node.split(":", 1)[0].replace("_", " ").title()
        for node in graph.nodes
        if node in highlighted or graph.degree(node) >= 4
    }
    nx.draw_networkx_labels(
        graph,
        position,
        labels=labels,
        font_size=7.2,
        font_weight="bold",
        font_color=INK,
        bbox={"facecolor": "white", "alpha": 0.74, "edgecolor": "none", "pad": 1.4},
        ax=axis,
    )
    axis.set_title("Identity attack-surface atlas", pad=18)
    axis.text(
        0.5,
        1.01,
        f"Union of {len(finding_ids)} high-ranked paths · {len(graph)} nodes · "
        "red = highest-ranked route",
        transform=axis.transAxes,
        ha="center",
        color=MUTED,
    )
    legend = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=color,
            label=kind.title(),
            markersize=8,
        )
        for kind, color in type_colors.items()
        if any(node.startswith(kind + ":") for node in graph.nodes)
    ]
    axis.legend(handles=legend, loc="lower center", ncol=min(7, len(legend)), frameon=False)
    save_figure(figure, output, "13_attack_surface_atlas")


def ztri_concentration_figure(runs_root: Path, output: Path) -> None:
    """Plot cumulative modeled risk mass among top-ranked identities."""
    by_profile: dict[str, list[np.ndarray]] = defaultdict(list)
    for directory in sorted(path for path in runs_root.glob("run-*") if path.is_dir()):
        manifest = json.loads((directory / "run_manifest.json").read_text(encoding="utf-8"))
        dataset = json.loads((directory / "dataset_manifest.json").read_text(encoding="utf-8"))
        if manifest["method"] != "graphtrust" or dataset["variant"] == "clean":
            continue
        scores = pl.read_parquet(directory / "identity_scores.parquet")["ztri"].to_numpy()
        scores = np.sort(np.clip(scores, 0, None))[::-1]
        if scores.size and scores.sum() > 0:
            by_profile[str(dataset["profile"])].append(scores)
    if not by_profile:
        unavailable_figure(
            output,
            "14_ztri_concentration",
            "Concentration of modeled identity risk",
            "No verified GraphTrust identity-score artifacts are available.",
        )
        return

    figure, axis = plt.subplots(figsize=(10, 6))
    palette = dict(zip(sorted(by_profile), (COLORS[0], COLORS[1], COLORS[3]), strict=False))
    grid = np.linspace(0, 1, 201)
    for profile, arrays in sorted(by_profile.items()):
        curves = []
        for scores in arrays:
            x = np.arange(1, len(scores) + 1) / len(scores)
            y = np.cumsum(scores) / scores.sum()
            curves.append(np.interp(grid, x, y, left=0, right=1))
        mean = np.mean(curves, axis=0)
        low, high = np.quantile(curves, (0.1, 0.9), axis=0)
        label = profile.replace("_", " ").title()
        axis.plot(grid * 100, mean * 100, lw=2.8, color=palette[profile], label=label)
        axis.fill_between(grid * 100, low * 100, high * 100, color=palette[profile], alpha=0.12)
    axis.plot([0, 100], [0, 100], ls="--", color="#94A3B8", lw=1, label="Uniform risk")
    axis.set_title("How concentrated is the modeled identity risk?")
    axis.set_xlabel("Top-ranked identities included (%)")
    axis.set_ylabel("Cumulative share of ZTRI mass (%)")
    axis.set(xlim=(0, 100), ylim=(0, 100))
    axis.grid(alpha=0.2)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(frameon=False, loc="lower right")
    save_figure(figure, output, "14_ztri_concentration")


def remediation_figure(artifact_root: Path, output: Path, tables: Path) -> None:
    plans: list[dict[str, Any]] = []
    for path in artifact_root.rglob("remediation_plans.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, list):
            plans.extend({"source_artifact": str(path), **plan} for plan in value)
    deduplicated: dict[str, dict[str, Any]] = {}
    for plan in plans:
        plan_id = str(plan.get("plan_id", plan.get("source_artifact")))
        previous = deduplicated.get(plan_id)
        if previous is None or (
            bool(plan.get("counterfactual_verified"))
            and not bool(previous.get("counterfactual_verified"))
        ):
            deduplicated[plan_id] = plan
    plans = list(deduplicated.values())
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
    figure, axis = plt.subplots(figsize=(9.6, 6))
    solvers = sorted({str(plan.get("solver")) for plan in plans})
    for index, solver in enumerate(solvers):
        values = [plan for plan in plans if plan.get("solver") == solver]
        for plan in values:
            verified = bool(plan.get("counterfactual_verified", False))
            x = float(plan["modeled_cost"])
            y = 1 - float(plan["residual_exposure"])
            axis.scatter(
                x,
                y,
                s=155,
                color=COLORS[index % len(COLORS)] if verified else "white",
                edgecolor=COLORS[index % len(COLORS)],
                linewidth=2.2,
                marker="o" if verified else "X",
                zorder=3,
            )
            axis.annotate(
                f"{solver.replace('_', ' ')}\n{len(plan.get('removed_edge_ids', []))} changes",
                (x, y),
                xytext=(7, 8),
                textcoords="offset points",
                fontsize=7.5,
                color=INK,
            )
    legend = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=INK,
            markeredgecolor=INK,
            markersize=8,
            label="counterfactually verified",
        ),
        Line2D(
            [0],
            [0],
            marker="X",
            color="none",
            markerfacecolor="white",
            markeredgecolor=INK,
            markersize=8,
            label="failed post-check",
        ),
    ]
    axis.set_xlabel("Modeled business-removal cost")
    axis.set_ylabel("Exposure reduction")
    axis.set_title("Cost-exposure frontier after applying proposed IAM changes")
    axis.legend(handles=legend, frameon=False, loc="lower right")
    axis.grid(alpha=0.2)
    axis.spines[["top", "right"]].set_visible(False)
    save_figure(figure, output, "06_remediation_frontier")


def runtime_and_ztri(runs_root: Path, output: Path, tables: Path) -> None:
    runtime_rows: list[dict[str, Any]] = []
    ztri_by_profile: dict[str, list[float]] = defaultdict(list)
    for directory in sorted(runs_root.glob("run-*")):
        if not directory.is_dir():
            continue
        manifest = json.loads((directory / "dataset_manifest.json").read_text(encoding="utf-8"))
        run_manifest = json.loads((directory / "run_manifest.json").read_text(encoding="utf-8"))
        timing = json.loads((directory / "timings.json").read_text(encoding="utf-8"))
        runtime_rows.append(
            {
                "run_id": directory.name,
                "scale": manifest["scale"],
                "profile": manifest["profile"],
                "method": run_manifest["method"],
                "nodes": manifest["realized_counts"].get("nodes", 0),
                **timing,
            }
        )
        scores = pl.read_parquet(directory / "identity_scores.parquet")
        if "ztri" in scores.columns and run_manifest["method"] == "graphtrust":
            ztri_by_profile[str(manifest["profile"])].extend(
                float(value) for value in scores["ztri"].to_list()
            )
    if runtime_rows:
        pl.DataFrame(runtime_rows).write_csv(tables / "05_runtime_and_memory.csv")
        figure, axis = plt.subplots(figsize=(9.6, 5.8))
        node_counts = sorted({int(row["nodes"]) for row in runtime_rows})
        if len(node_counts) == 1:
            data = []
            labels = []
            for method in METHOD_ORDER:
                values = [
                    float(row["inference_seconds"])
                    for row in runtime_rows
                    if row["method"] == method
                ]
                if values:
                    data.append(values)
                    labels.append(METHOD_LABELS[method])
            axis.boxplot(data, tick_labels=labels, patch_artist=True, widths=0.55)
            axis.set_ylabel("Inference seconds")
            axis.set_title(f"Runtime distribution on fixed {node_counts[0]:,}-node graphs")
            axis.tick_params(axis="x", rotation=18)
        else:
            for method in METHOD_ORDER:
                selected = [row for row in runtime_rows if row["method"] == method]
                if not selected:
                    continue
                axis.scatter(
                    [row["nodes"] for row in selected],
                    [row["inference_seconds"] for row in selected],
                    s=42,
                    c=METHOD_COLORS[method],
                    alpha=0.72,
                    edgecolors="white",
                    linewidths=0.7,
                    label=METHOD_LABELS[method],
                )
            axis.set_xscale("log")
            axis.set_yscale("log")
            axis.set_xlabel("Nodes")
            axis.set_ylabel("Inference seconds")
            axis.set_title("Runtime scaling across graph sizes")
            axis.legend(frameon=False, ncols=2)
        axis.grid(alpha=0.2)
        axis.spines[["top", "right"]].set_visible(False)
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
    if ztri_by_profile:
        figure, axis = plt.subplots(figsize=(9.6, 5.8))
        bins = np.linspace(0, 100, 41).tolist()
        for index, (profile, values) in enumerate(sorted(ztri_by_profile.items())):
            axis.hist(
                values,
                bins=bins,
                density=True,
                histtype="stepfilled",
                alpha=0.28,
                color=COLORS[index],
                label=profile.replace("_", " ").title(),
            )
            axis.hist(
                values, bins=bins, density=True, histtype="step", linewidth=1.8, color=COLORS[index]
            )
        axis.set_xlabel("ZTRI")
        axis.set_ylabel("Density")
        axis.set_title("Whole-identity risk distributions by enterprise profile")
        axis.legend(frameon=False)
        axis.spines[["top", "right"]].set_visible(False)
        save_figure(figure, output, "08_ztri_distribution")
    else:
        unavailable_figure(
            output,
            "08_ztri_distribution",
            "ZTRI distribution",
            "No verified identity-score artifacts are available.",
        )


def profile_method_heatmap(rows: list[dict[str, Any]], output: Path) -> None:
    """Show whether method ordering changes across organization profiles."""
    if not rows:
        unavailable_figure(
            output,
            "11_profile_method_heatmap",
            "Profile x method detection",
            "No verified runs are available.",
        )
        return
    profiles = sorted({str(row["profile"]) for row in rows})
    methods = [method for method in METHOD_ORDER if any(row["method"] == method for row in rows)]
    matrix = np.full((len(profiles), len(methods)), np.nan)
    for i, profile in enumerate(profiles):
        for j, method in enumerate(methods):
            values = [
                float(row["risky_starting_identity_recall"])
                for row in rows
                if row["profile"] == profile and row["method"] == method
            ]
            if values:
                matrix[i, j] = float(np.mean(values))
    figure, axis = plt.subplots(figsize=(10, 4.8))
    image = axis.imshow(matrix, cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
    for i in range(len(profiles)):
        for j in range(len(methods)):
            if np.isfinite(matrix[i, j]):
                axis.text(
                    j,
                    i,
                    f"{matrix[i, j]:.2f}",
                    ha="center",
                    va="center",
                    color="white" if matrix[i, j] > 0.55 else INK,
                    weight="bold",
                    fontsize=9,
                )
    axis.set_xticks(
        range(len(methods)), [METHOD_LABELS[m] for m in methods], rotation=18, ha="right"
    )
    axis.set_yticks(range(len(profiles)), [p.replace("_", " ").title() for p in profiles])
    axis.set_title("Risky-identity recall changes with enterprise structure")
    figure.colorbar(image, ax=axis, label="Mean recall", fraction=0.025, pad=0.03)
    save_figure(figure, output, "11_profile_method_heatmap")


def paired_difference_figure(rows: list[dict[str, Any]], output: Path) -> None:
    """Plot graph-level paired differences instead of only aggregate rankings."""
    by_key: dict[tuple[object, ...], dict[str, float]] = defaultdict(dict)
    for row in rows:
        key = (row["profile"], row["scale"], row["seed"], row["variant"])
        by_key[key][str(row["method"])] = float(row["risky_starting_identity_recall"])
    baselines = [method for method in METHOD_ORDER if method != "graphtrust"]
    differences = {
        baseline: [
            methods["graphtrust"] - methods[baseline]
            for methods in by_key.values()
            if "graphtrust" in methods and baseline in methods
        ]
        for baseline in baselines
    }
    if not any(differences.values()):
        unavailable_figure(
            output,
            "12_paired_differences",
            "Paired GraphTrust differences",
            "Complete paired runs are not yet available.",
        )
        return
    figure, axis = plt.subplots(figsize=(9.6, 5.8))
    rng = np.random.default_rng(104729)
    for index, baseline in enumerate(baselines):
        values = np.asarray(differences[baseline], dtype=float)
        if not values.size:
            continue
        jitter = rng.uniform(-0.11, 0.11, size=values.size)
        axis.scatter(
            np.full(values.size, index) + jitter,
            values,
            s=28,
            alpha=0.38,
            color=METHOD_COLORS[baseline],
            edgecolor="none",
        )
        median = float(np.median(values))
        axis.plot(
            [index - 0.23, index + 0.23],
            [median, median],
            color=INK,
            lw=3.2,
            solid_capstyle="round",
        )
        axis.text(
            index, median + 0.035, f"median {median:+.2f}", ha="center", fontsize=8, weight="bold"
        )
    axis.axhline(0, color="#475569", lw=1.2, ls="--")
    axis.set_xticks(range(len(baselines)), [f"vs {METHOD_LABELS[b]}" for b in baselines])
    axis.set_ylabel("Paired difference in risky-identity recall")
    axis.set_title("Where GraphTrust gains—and where it does not")
    axis.grid(axis="y", alpha=0.18)
    axis.spines[["top", "right", "left"]].set_visible(False)
    save_figure(figure, output, "12_paired_differences")


def extended_figures(artifact_root: Path, output: Path, tables: Path) -> None:
    ablations: list[dict[str, Any]] = []
    sensitivity: list[dict[str, Any]] = []
    dirichlet: list[dict[str, Any]] = []
    for path in artifact_root.glob("extended/extended-*/ablation_results.json"):
        ablations.extend(json.loads(path.read_text(encoding="utf-8")))
    for path in artifact_root.glob("extended/extended-*/sensitivity_results.json"):
        loaded = json.loads(path.read_text(encoding="utf-8"))
        sensitivity.extend(loaded["one_at_a_time"])
        dirichlet.extend(loaded.get("dirichlet_1000", []))
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
        figure, axes = plt.subplots(
            1, 2, figsize=(11.5, 5.2), gridspec_kw={"width_ratios": [1.35, 1]}
        )
        axis = axes[0]
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
        axis.set_title("One-at-a-time perturbations")
        axis.grid(axis="y", alpha=0.2)
        distribution = axes[1]
        if dirichlet:
            correlations = [float(row["spearman"]) for row in dirichlet]
            distribution.hist(correlations, bins=28, color=COLORS[3], alpha=0.78, edgecolor="white")
            distribution.axvline(
                float(np.median(correlations)),
                color=INK,
                lw=2,
                ls="--",
                label=f"median {np.median(correlations):.2f}",
            )
            distribution.set_xlabel("Spearman rank correlation")
            distribution.set_ylabel("Dirichlet samples")
            distribution.set_title("1,000 random ZTRI weights")
            distribution.legend(frameon=False)
            distribution.spines[["top", "right"]].set_visible(False)
        figure.suptitle("Sensitivity and ranking stability", fontsize=15, weight="bold")
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
    review_budget_figure(rows, arguments.output, tables)
    artifact_root = arguments.runs.parent
    remediation_figure(artifact_root, arguments.output, tables)
    runtime_and_ztri(arguments.runs, arguments.output, tables)
    extended_figures(artifact_root, arguments.output, tables)
    profile_method_heatmap(rows, arguments.output)
    paired_difference_figure(rows, arguments.output)
    depth_stratified_figure(arguments.runs, arguments.output, tables)
    attack_surface_atlas(arguments.runs, arguments.output)
    ztri_concentration_figure(arguments.runs, arguments.output)
    print(arguments.output)


if __name__ == "__main__":
    main()
