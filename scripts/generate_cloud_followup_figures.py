from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


COLORS = {
    "min_cut": "#16a34a",
    "risk_greedy": "#0284c7",
    "constraint_generation": "#7c3aed",
    "degree_greedy": "#d97706",
    "graphtrust": "#16a34a",
    "untyped": "#0284c7",
    "native_scope": "#7c3aed",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "#f8fafc",
            "axes.edgecolor": "#94a3b8",
            "axes.labelcolor": "#0f172a",
            "text.color": "#0f172a",
            "xtick.color": "#334155",
            "ytick.color": "#334155",
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titleweight": "bold",
            "axes.titlepad": 14,
            "axes.grid": True,
            "grid.color": "#cbd5e1",
            "grid.alpha": 0.55,
            "grid.linestyle": "--",
        }
    )


def remediation_figure(rows: list[dict[str, str]], output: Path) -> None:
    labels = {
        "min_cut": "Weighted min-cut",
        "risk_greedy": "Risk greedy",
        "constraint_generation": "Constraint generation",
        "degree_greedy": "Degree greedy",
    }
    order = tuple(labels)
    selected = [row for row in rows if float(row["target_fraction"]) == 0.95]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in selected:
        grouped[row["solver"]].append(row)

    means = [
        np.mean([float(row["achieved_exposure_reduction"]) for row in grouped[key]])
        for key in order
    ]
    costs = [
        np.mean([float(row["modeled_cost"]) for row in grouped[key]]) for key in order
    ]
    changes = [
        np.mean([float(row["changes"]) for row in grouped[key]]) for key in order
    ]
    runtimes = [
        np.mean([float(row["runtime_seconds"]) for row in grouped[key]])
        for key in order
    ]

    fig, ax = plt.subplots(figsize=(10.6, 6.3))
    fig.subplots_adjust(left=0.10, right=0.98, top=0.88, bottom=0.22)
    positions = np.arange(len(order))
    bars = ax.bar(
        positions,
        np.asarray(means) * 100,
        color=[COLORS[key] for key in order],
        width=0.66,
    )
    ax.axhline(
        95,
        color="#dc2626",
        linewidth=1.8,
        linestyle=(0, (5, 4)),
        label="Requested target (95%)",
    )
    ax.set_ylim(0, 104)
    ax.set_ylabel("Mean achieved weighted exposure reduction (%)")
    ax.set_xticks(positions, [labels[key] for key in order])
    ax.set_title("Replicated remediation across 15 frozen organizations")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right", frameon=False)
    for index, bar in enumerate(bars):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1.2,
            f"{means[index] * 100:.2f}%",
            ha="center",
            fontweight="bold",
        )
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            4,
            f"cost {costs[index]:.2f}\n{changes[index]:.1f} changes\n{runtimes[index]:.2f} s",
            ha="center",
            va="bottom",
            fontsize=8.5,
            color="white" if bar.get_height() > 20 else "#0f172a",
            fontweight="bold",
        )
    fig.text(
        0.5,
        0.035,
        "All counterfactuals and workflows verified; requested-target attainment is reported separately.",
        ha="center",
        color="#475569",
        fontsize=8.5,
    )
    fig.savefig(output / "17_remediation_replication.png", dpi=300, bbox_inches="tight")
    fig.savefig(output / "17_remediation_replication.svg", bbox_inches="tight")
    plt.close(fig)


def depth_figure(rows: list[dict[str, str]], output: Path) -> None:
    labels = {
        "graphtrust": "GraphTrust",
        "untyped": "Untyped",
        "native_scope": "Native scope",
    }
    selected = [
        row
        for row in rows
        if int(row["analysis_depth"]) == 6 and row["method"] in labels
    ]
    grouped: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in selected:
        grouped[(row["method"], int(row["path_depth"]))].append(float(row["recall"]))
    depths = (2, 3, 4)

    fig, ax = plt.subplots(figsize=(9.8, 6.0))
    fig.subplots_adjust(left=0.10, right=0.98, top=0.88, bottom=0.19)
    markers = {"graphtrust": "o", "untyped": "s", "native_scope": "^"}
    for method in labels:
        means = [np.mean(grouped[(method, depth)]) * 100 for depth in depths]
        ax.plot(
            depths,
            means,
            label=labels[method],
            color=COLORS[method],
            marker=markers[method],
            linewidth=3,
            markersize=8,
        )
        for depth, mean in zip(depths, means, strict=True):
            ax.annotate(
                f"{mean:.1f}%",
                (depth, mean),
                xytext=(0, 9),
                textcoords="offset points",
                ha="center",
                fontsize=8.5,
                fontweight="bold",
            )
    ax.set_xlim(1.8, 4.2)
    ax.set_ylim(0, 104)
    ax.set_xticks(depths)
    ax.set_xlabel("Planted path depth")
    ax.set_ylabel("Mean exact-path recall (%)")
    ax.set_title("Depth-stratified exact-path recall at analysis depth 6")
    ax.legend(frameon=False, ncol=3, loc="upper right")
    fig.text(
        0.5,
        0.03,
        "n = 15 independent organizations. Direct and privileged-only recall = 0; no depth-1 planted risk exists.",
        ha="center",
        color="#475569",
        fontsize=8.5,
    )
    fig.savefig(output / "18_depth_stratified_recall.png", dpi=300, bbox_inches="tight")
    fig.savefig(output / "18_depth_stratified_recall.svg", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    style()
    remediation_figure(
        read_csv(args.evidence / "remediation_replication_15_graphs.csv"), args.output
    )
    depth_figure(read_csv(args.evidence / "depth_stress_15_graphs.csv"), args.output)


if __name__ == "__main__":
    main()
