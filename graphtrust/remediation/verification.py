"""Counterfactual remediation verification utilities."""

from collections.abc import Sequence
from dataclasses import dataclass

from graphtrust.graph.protocol import CapabilityGraphBackend
from graphtrust.remediation.problem import RemediationProblem, stable_plan_id
from graphtrust.schemas.remediation import RemediationPlan, SolverName, SolverStatus


def backend_without_raw_edges(
    backend: CapabilityGraphBackend,
    removed_raw_edge_ids: Sequence[str],
) -> CapabilityGraphBackend:
    """Remove every derived transition that relies on a removed raw relationship."""
    removed = set(removed_raw_edge_ids)
    effective_to_remove = tuple(
        edge.edge_id for edge in backend.edges() if removed.intersection(edge.raw_evidence_edge_ids)
    )
    return backend.without_edges(effective_to_remove)


def blocked_finding_ids(
    problem: RemediationProblem,
    removed_raw_edge_ids: Sequence[str],
) -> tuple[str, ...]:
    removed = set(removed_raw_edge_ids)
    return tuple(
        path.path_id
        for path in problem.dangerous_paths()
        if removed.intersection(path.raw_edge_ids)
    )


def exposure_reduction(
    problem: RemediationProblem,
    removed_raw_edge_ids: Sequence[str],
) -> float:
    removed = set(removed_raw_edge_ids)
    paths = problem.dangerous_paths()
    total = sum(path.relative_exposure for path in paths)
    blocked = sum(
        path.relative_exposure for path in paths if removed.intersection(path.raw_edge_ids)
    )
    return blocked / total if total else 1.0


@dataclass(frozen=True, slots=True)
class ReachabilityVerification:
    verified: bool
    remaining_pairs: tuple[tuple[str, str], ...]


def verify_source_target_reachability(
    problem: RemediationProblem,
    removed_raw_edge_ids: Sequence[str],
    *,
    maximum_depth: int = 8,
) -> ReachabilityVerification:
    """Apply removals and rerun bounded reachability for every declared pair."""
    reduced = backend_without_raw_edges(problem.backend, removed_raw_edge_ids)
    remaining: list[tuple[str, str]] = []
    target_set = set(problem.target_ids)
    for source_id in problem.source_ids:
        reachable = reduced.reachable((source_id,), maximum_depth=maximum_depth)
        remaining.extend(
            (source_id, target_id) for target_id in sorted(target_set.intersection(reachable))
        )
    return ReachabilityVerification(not remaining, tuple(remaining))


def build_verified_plan(
    problem: RemediationProblem,
    *,
    solver: SolverName,
    removed_edge_ids: tuple[str, ...],
    target_fraction: float,
    runtime_seconds: float,
    status: SolverStatus = SolverStatus.FEASIBLE,
    maximum_depth: int = 8,
) -> RemediationPlan:
    """Build a plan only after path, reachability, and workflow verification."""
    from graphtrust.remediation.business_constraints import verify_business_requirements

    raw_by_id = problem.raw_edge_by_id
    blocked_ids = blocked_finding_ids(problem, removed_edge_ids)
    blocked_fraction = len(blocked_ids) / len(problem.findings) if problem.findings else 1.0
    reachability = verify_source_target_reachability(
        problem,
        removed_edge_ids,
        maximum_depth=maximum_depth,
    )
    business = verify_business_requirements(problem, removed_edge_ids)
    target_verified = (
        reachability.verified if target_fraction == 1.0 else blocked_fraction >= target_fraction
    )
    node_by_id = problem.node_by_id
    affected = tuple(
        sorted(
            {
                node_by_id[raw_by_id[edge_id].source_id].department
                for edge_id in removed_edge_ids
                if edge_id in raw_by_id and raw_by_id[edge_id].source_id in node_by_id
            }
        )
    )
    return RemediationPlan(
        plan_id=stable_plan_id(solver.value, removed_edge_ids),
        solver=solver,
        status=status,
        removed_edge_ids=removed_edge_ids,
        modeled_cost=sum(
            raw_by_id[edge_id].business_removal_cost
            for edge_id in removed_edge_ids
            if edge_id in raw_by_id
        ),
        blocked_path_ids=blocked_ids,
        residual_exposure=max(0.0, 1.0 - exposure_reduction(problem, removed_edge_ids)),
        affected_departments=affected,
        protected_workflows_preserved=business.valid,
        counterfactual_verified=target_verified and business.valid,
        runtime_seconds=runtime_seconds,
    )
