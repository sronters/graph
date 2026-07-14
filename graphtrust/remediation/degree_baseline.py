"""B4 degree-priority remediation baseline."""

import time
from collections import Counter, defaultdict

from graphtrust.remediation.problem import RemediationProblem
from graphtrust.remediation.verification import (
    backend_without_raw_edges,
    blocked_finding_ids,
    build_verified_plan,
)
from graphtrust.schemas.remediation import RemediationPlan, SolverName


def solve_degree_greedy(
    problem: RemediationProblem,
    *,
    target_fraction: float = 1.0,
    maximum_depth: int = 8,
) -> RemediationPlan:
    """Remove evidence incident to the current highest-degree noncritical node."""
    started = time.perf_counter()
    candidates = problem.removable_edges()
    selected: list[str] = []
    critical = set(problem.target_ids)
    while len(blocked_finding_ids(problem, selected)) < target_fraction * len(problem.findings):
        current = backend_without_raw_edges(problem.backend, selected)
        degree: Counter[str] = Counter()
        incident_by_raw_edge: dict[str, set[str]] = defaultdict(set)
        for effective in current.edges():
            degree[effective.actor_before] += 1
            degree[effective.resource_or_identity_target] += 1
            incident_nodes = {
                endpoint
                for endpoint in (
                    effective.actor_before,
                    effective.resource_or_identity_target,
                )
                if endpoint not in critical
            }
            for raw_edge_id in effective.raw_evidence_edge_ids:
                if raw_edge_id in candidates and raw_edge_id not in selected:
                    incident_by_raw_edge[raw_edge_id].update(incident_nodes)
        ranked: list[tuple[int, float, str]] = []
        for edge_id, raw in candidates.items():
            if edge_id in selected:
                continue
            incident_nodes = incident_by_raw_edge.get(edge_id, set())
            if incident_nodes:
                ranked.append(
                    (
                        max(degree[node_id] for node_id in incident_nodes),
                        -raw.business_removal_cost,
                        edge_id,
                    )
                )
        if not ranked:
            break
        selected.append(max(ranked)[2])
    return build_verified_plan(
        problem,
        solver=SolverName.DEGREE_GREEDY,
        removed_edge_ids=tuple(sorted(selected)),
        target_fraction=target_fraction,
        runtime_seconds=time.perf_counter() - started,
        maximum_depth=maximum_depth,
    )
