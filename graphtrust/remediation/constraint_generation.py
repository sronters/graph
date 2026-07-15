"""Iterative verification and constraint generation for omitted paths."""

import hashlib
import time

from graphtrust.analysis.paths import top_k_loopless_paths
from graphtrust.remediation.business_constraints import verify_business_requirements
from graphtrust.remediation.path_hitting_set import solve_path_hitting_set
from graphtrust.remediation.problem import DangerousPath, RemediationProblem
from graphtrust.remediation.verification import backend_without_raw_edges
from graphtrust.schemas.remediation import (
    RemediationConstraints,
    RemediationPlan,
    SolverName,
    SolverStatus,
)


def _remaining_violating_path(
    problem: RemediationProblem,
    removed: tuple[str, ...],
    *,
    maximum_depth: int,
) -> DangerousPath | None:
    reduced = backend_without_raw_edges(problem.backend, removed)
    for source_id in problem.source_ids:
        for target_id in problem.target_ids:
            result = top_k_loopless_paths(
                reduced,
                source_id,
                target_id,
                maximum_depth=maximum_depth,
                top_k=1,
                expansion_cap=100_000,
                weight_mode="untyped",
            )
            if not result.paths:
                continue
            path = result.paths[0]
            raw_ids = frozenset(
                raw_id for edge in path.edges for raw_id in edge.raw_evidence_edge_ids
            )
            digest = hashlib.sha256("\0".join(sorted(raw_ids)).encode()).hexdigest()[:16]
            return DangerousPath(
                path_id=f"generated:{digest}",
                raw_edge_ids=raw_ids,
                relative_exposure=0.0,
            )
    return None


def solve_with_constraint_generation(
    problem: RemediationProblem,
    *,
    target_fraction: float = 1.0,
    constraints: RemediationConstraints | None = None,
    time_limit_seconds: float = 120.0,
    iteration_cap: int = 100,
    maximum_depth: int = 8,
) -> RemediationPlan:
    """Solve, apply, search for violations, and add constraints until verified."""
    started = time.perf_counter()
    resolved_constraints = constraints or RemediationConstraints()
    added_paths: list[DangerousPath] = []
    forbidden: list[frozenset[str]] = []
    last_plan: RemediationPlan | None = None
    for iteration in range(1, iteration_cap + 1):
        remaining_time = max(0.01, time_limit_seconds - (time.perf_counter() - started))
        plan = solve_path_hitting_set(
            problem,
            target_fraction=target_fraction,
            constraints=resolved_constraints,
            time_limit_seconds=remaining_time,
            additional_paths=added_paths,
            forbidden_solutions=forbidden,
            solver_name=SolverName.CONSTRAINT_GENERATION,
            maximum_depth=maximum_depth,
        )
        last_plan = plan
        if plan.status in {SolverStatus.INFEASIBLE, SolverStatus.TIME_LIMIT, SolverStatus.ERROR}:
            return plan.model_copy(
                update={"iterations": iteration, "added_constraints": len(added_paths)}
            )
        business = verify_business_requirements(problem, plan.removed_edge_ids)
        if not business.valid:
            forbidden.append(frozenset(plan.removed_edge_ids))
            continue
        if target_fraction < 1.0:
            return plan.model_copy(
                update={
                    "iterations": iteration,
                    "added_constraints": len(added_paths),
                    "runtime_seconds": time.perf_counter() - started,
                }
            )
        violation = _remaining_violating_path(
            problem,
            plan.removed_edge_ids,
            maximum_depth=maximum_depth,
        )
        if violation is None:
            return plan.model_copy(
                update={
                    "counterfactual_verified": True,
                    "iterations": iteration,
                    "added_constraints": len(added_paths),
                    "runtime_seconds": time.perf_counter() - started,
                }
            )
        if not violation.raw_edge_ids.intersection(problem.removable_edges()):
            return plan.model_copy(
                update={
                    "status": SolverStatus.INFEASIBLE,
                    "counterfactual_verified": False,
                    "iterations": iteration,
                    "added_constraints": len(added_paths),
                    "runtime_seconds": time.perf_counter() - started,
                    "caveats": (*plan.caveats, "A remaining path contains no removable edge."),
                }
            )
        if violation.raw_edge_ids not in {path.raw_edge_ids for path in added_paths}:
            added_paths.append(violation)
        if time.perf_counter() - started >= time_limit_seconds:
            return plan.model_copy(
                update={
                    "status": SolverStatus.TIME_LIMIT,
                    "counterfactual_verified": False,
                    "iterations": iteration,
                    "added_constraints": len(added_paths),
                    "runtime_seconds": time.perf_counter() - started,
                }
            )
    if last_plan is None:
        raise RuntimeError("constraint generation did not execute")
    return last_plan.model_copy(
        update={
            "status": SolverStatus.TIME_LIMIT,
            "counterfactual_verified": False,
            "iterations": iteration_cap,
            "added_constraints": len(added_paths),
            "runtime_seconds": time.perf_counter() - started,
        }
    )
