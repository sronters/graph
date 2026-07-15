"""Replicate counterfactual remediation across frozen injected graphs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import polars as pl

from graphtrust.remediation.factory import build_remediation_problem
from graphtrust.remediation.runner import run_remediation_methods
from graphtrust.schemas.remediation import RemediationConstraints, SolverName
from graphtrust.settings import load_project_config


def run(
    dataset_root: Path,
    config_path: Path,
    output: Path,
    targets: tuple[float, ...],
    solvers: tuple[SolverName, ...],
) -> None:
    config = load_project_config(config_path)
    datasets = sorted(
        path
        for path in dataset_root.rglob("injected_mixed")
        if path.is_dir() and (path / "manifest.json").is_file()
    )
    rows: list[dict[str, object]] = []
    for dataset_path in datasets:
        problem = build_remediation_problem(dataset_path, config)
        runs = run_remediation_methods(
            problem,
            solvers=solvers,
            targets=targets,
            constraints=RemediationConstraints(),
            maximum_depth=config.analysis.maximum_depth,
        )
        manifest = json.loads((dataset_path / "manifest.json").read_text(encoding="utf-8"))
        for execution in runs:
            plan = execution.plan
            rows.append(
                {
                    "dataset_id": manifest["dataset_id"],
                    "profile": manifest["profile"],
                    "seed": manifest["generator_seed"],
                    "target_fraction": execution.target_fraction,
                    "solver": execution.solver.value,
                    "status": plan.status.value,
                    "counterfactual_verified": plan.counterfactual_verified,
                    "protected_workflows_preserved": plan.protected_workflows_preserved,
                    "achieved_exposure_reduction": 1.0 - plan.residual_exposure,
                    "modeled_cost": plan.modeled_cost,
                    "changes": len(plan.removed_edge_ids),
                    "departments_affected": len(plan.affected_departments),
                    "runtime_seconds": plan.runtime_seconds,
                    "infeasible_or_timeout": plan.status.value in {"INFEASIBLE", "TIME_LIMIT"},
                }
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).write_csv(output)
    print(json.dumps({"datasets": len(datasets), "plans": len(rows), "output": str(output)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("data/generated"))
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/evidence/remediation_replication.csv"),
    )
    parser.add_argument("--targets", default="0.50,0.70,0.80,0.90,0.95")
    parser.add_argument(
        "--solvers",
        default=",".join(solver.value for solver in SolverName),
        help=(
            "Comma-separated solver names; constraint_generation can be expensive on large queues."
        ),
    )
    args = parser.parse_args()
    targets = tuple(float(value) for value in args.targets.split(",") if value.strip())
    solvers = tuple(SolverName(value) for value in args.solvers.split(",") if value.strip())
    run(args.dataset_root, args.config, args.output, targets, solvers)


if __name__ == "__main__":
    main()
