"""Truth-safe analysis and remediation application services."""

from pathlib import Path
from typing import Any

from graphtrust.analysis.pipeline import DatasetAnalysis, analyze_bundle
from graphtrust.api.repository import ApiRepository
from graphtrust.data import read_dataset
from graphtrust.remediation.factory import build_remediation_problem
from graphtrust.remediation.runner import run_remediation_methods
from graphtrust.remediation.verification import (
    exposure_reduction,
    verify_source_target_reachability,
)
from graphtrust.schemas.findings import AnalysisMethod
from graphtrust.schemas.remediation import SolverName
from graphtrust.settings import ProjectConfig


def serialize_analysis(analysis: DatasetAnalysis) -> dict[str, Any]:
    """Build one restart-safe result snapshot for API reads."""
    node_by_id = {node.node_id: node for node in analysis.records.nodes}
    identities: list[dict[str, Any]] = []
    paths: list[dict[str, Any]] = []
    method_summaries: dict[str, dict[str, Any]] = {}
    for method, result in analysis.results.items():
        method_summaries[method.value] = {
            "findings": len(result.findings),
            "risky_starting_identities": len(result.reachability),
            "search_complete": result.search_complete,
            "expanded_states": result.expanded_states,
            "warnings": result.warnings,
        }
        for score in result.identity_scores:
            node = node_by_id[score.node_id]
            identities.append(
                {
                    "method": method.value,
                    **node.model_dump(mode="json"),
                    **score.model_dump(mode="json"),
                }
            )
        paths.extend(finding.model_dump(mode="json") for finding in result.findings)
    identities.sort(key=lambda row: (-float(row["ztri"]), str(row["node_id"]), str(row["method"])))
    paths.sort(key=lambda row: (-float(row["risk"]["path_risk"]), str(row["finding_id"])))
    return {
        "summary": {
            "effective_edges": len(analysis.compilation.effective_edges),
            "rejected_semantic_edges": len(analysis.compilation.rejected_edges),
            "methods": method_summaries,
        },
        "identities": identities,
        "paths": paths,
    }


def execute_analysis_job(
    repository: ApiRepository,
    analysis_id: str,
    dataset_path: Path,
    methods: tuple[AnalysisMethod, ...],
    config: ProjectConfig,
) -> None:
    """Persist every job transition so an API restart cannot lose status."""
    repository.mark_running(analysis_id)
    try:
        bundle = read_dataset(dataset_path)
        analysis = analyze_bundle(bundle, config, methods)
        repository.mark_succeeded(analysis_id, serialize_analysis(analysis))
    except Exception as error:  # background boundary must persist all ordinary failures
        repository.mark_failed(analysis_id, f"{type(error).__name__}: {error}")


def remediate(
    dataset_path: Path,
    config: ProjectConfig,
    solvers: tuple[SolverName, ...],
    targets: tuple[float, ...],
) -> tuple[dict[str, Any], ...]:
    problem = build_remediation_problem(dataset_path, config)
    runs = run_remediation_methods(
        problem,
        solvers=solvers,
        targets=targets,
        maximum_depth=config.analysis.maximum_depth,
    )
    return tuple(
        {"target_fraction": run.target_fraction, **run.plan.model_dump(mode="json")} for run in runs
    )


def counterfactual(
    dataset_path: Path,
    config: ProjectConfig,
    removed_edge_ids: tuple[str, ...],
) -> dict[str, Any]:
    problem = build_remediation_problem(dataset_path, config)
    known = problem.removable_edges()
    unknown = sorted(set(removed_edge_ids).difference(known))
    if unknown:
        raise ValueError(f"Unknown or non-removable edge IDs: {', '.join(unknown[:10])}")
    verification = verify_source_target_reachability(
        problem,
        removed_edge_ids,
        maximum_depth=config.analysis.maximum_depth,
    )
    return {
        "removed_edge_ids": removed_edge_ids,
        "exposure_reduction": exposure_reduction(problem, removed_edge_ids),
        "all_declared_pairs_blocked": verification.verified,
        "remaining_pairs": verification.remaining_pairs,
        "recommendation_only": True,
    }
