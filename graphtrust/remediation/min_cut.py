"""Fast weighted source-to-critical-target cut with counterfactual verification."""

import time
from collections import defaultdict

import networkx as nx

from graphtrust.remediation.business_constraints import verify_business_requirements
from graphtrust.remediation.problem import RemediationProblem, stable_plan_id
from graphtrust.remediation.verification import (
    blocked_finding_ids,
    exposure_reduction,
    verify_source_target_reachability,
)
from graphtrust.schemas.remediation import RemediationPlan, SolverName, SolverStatus


def solve_weighted_min_cut(
    problem: RemediationProblem,
    *,
    target_fraction: float = 1.0,
    maximum_depth: int = 8,
) -> RemediationPlan:
    """Solve the modeled weighted cut and verify it on the capability graph."""
    if not 0 < target_fraction <= 1:
        raise ValueError("target_fraction must be in (0, 1]")
    started = time.perf_counter()
    removable = problem.removable_edges()
    finite_total = sum(edge.business_removal_cost for edge in removable.values())
    infinite = finite_total + 1.0
    graph: nx.DiGraph[str] = nx.DiGraph()
    source = "__graphtrust_super_source__"
    sink = "__graphtrust_super_sink__"
    chosen_raw_by_gate: dict[str, str] = {}

    for effective in problem.backend.edges():
        candidates = [
            removable[raw_id]
            for raw_id in effective.business_removal_candidates
            if raw_id in removable
        ]
        if candidates:
            selected = min(candidates, key=lambda edge: (edge.business_removal_cost, edge.edge_id))
            capacity = selected.business_removal_cost
            chosen_raw = selected.edge_id
        else:
            capacity = infinite
            chosen_raw = ""
        gate = f"__effective_gate__:{effective.edge_id}"
        graph.add_edge(effective.actor_before, gate, capacity=capacity)
        graph.add_edge(gate, effective.resource_or_identity_target, capacity=infinite)
        chosen_raw_by_gate[gate] = chosen_raw
    for source_id in problem.source_ids:
        graph.add_edge(source, source_id, capacity=infinite)
    for target_id in problem.target_ids:
        graph.add_edge(target_id, sink, capacity=infinite)

    if not problem.source_ids or not problem.target_ids:
        removed: tuple[str, ...] = ()
        cut_value = 0.0
    else:
        cut_value, partition = nx.minimum_cut(graph, source, sink, capacity="capacity")
        reachable, non_reachable = partition
        cut_gates = [
            target
            for node_id in reachable
            for target in graph.successors(node_id)
            if target in non_reachable and target in chosen_raw_by_gate
        ]
        removed = tuple(
            sorted({chosen_raw_by_gate[gate] for gate in cut_gates if chosen_raw_by_gate[gate]})
        )

    reachability = verify_source_target_reachability(
        problem,
        removed,
        maximum_depth=maximum_depth,
    )
    business = verify_business_requirements(problem, removed)
    blocked_ids = blocked_finding_ids(problem, removed)
    blocked_fraction = len(blocked_ids) / len(problem.findings) if problem.findings else 1.0
    raw_by_id = problem.raw_edge_by_id
    modeled_cost = sum(raw_by_id[edge_id].business_removal_cost for edge_id in removed)
    affected = tuple(
        sorted(
            {
                problem.node_by_id[raw_by_id[edge_id].source_id].department
                for edge_id in removed
                if raw_by_id[edge_id].source_id in problem.node_by_id
            }
        )
    )
    target_verified = (
        reachability.verified if target_fraction == 1.0 else blocked_fraction >= target_fraction
    )
    verified = target_verified and business.valid
    caveats = [
        "Recommendation only; no live permission changes are executed.",
        "Optimality is relative to modeled costs and constraints.",
    ]
    shared_candidates: dict[str, int] = defaultdict(int)
    for effective in problem.backend.edges():
        for raw_id in effective.business_removal_candidates:
            shared_candidates[raw_id] += 1
    has_shared_raw_evidence = any(count > 1 for count in shared_candidates.values())
    status = (
        SolverStatus.OPTIMAL
        if verified and cut_value < infinite and not has_shared_raw_evidence
        else SolverStatus.FEASIBLE
    )
    if has_shared_raw_evidence:
        caveats.append(
            "Shared raw evidence can support multiple effective transitions; the cut is verified "
            "counterfactually after mapping gates to raw changes."
        )
    return RemediationPlan(
        plan_id=stable_plan_id(SolverName.MIN_CUT.value, removed),
        solver=SolverName.MIN_CUT,
        status=status,
        removed_edge_ids=removed,
        modeled_cost=modeled_cost,
        blocked_path_ids=blocked_ids,
        residual_exposure=max(0.0, 1.0 - exposure_reduction(problem, removed)),
        affected_departments=affected,
        protected_workflows_preserved=business.valid,
        counterfactual_verified=verified,
        optimality_bound=cut_value,
        optimality_gap=0.0 if status is SolverStatus.OPTIMAL else None,
        runtime_seconds=time.perf_counter() - started,
        caveats=tuple(caveats),
    )
