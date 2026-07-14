"""B5 risk-reduction-per-cost greedy remediation baseline."""

import time
from collections import defaultdict

from graphtrust.remediation.problem import RemediationProblem
from graphtrust.remediation.verification import build_verified_plan
from graphtrust.schemas.remediation import RemediationPlan, SolverName


def solve_risk_greedy(
    problem: RemediationProblem,
    *,
    target_fraction: float = 1.0,
    maximum_depth: int = 8,
) -> RemediationPlan:
    """Recompute marginal retained-exposure reduction after every raw-edge choice."""
    started = time.perf_counter()
    candidates = problem.removable_edges()
    paths = problem.dangerous_paths()
    paths_by_edge = defaultdict(list)
    for path in paths:
        for edge_id in path.raw_edge_ids:
            if edge_id in candidates:
                paths_by_edge[edge_id].append(path)
    selected: set[str] = set()
    blocked: set[str] = set()
    required = target_fraction * len(paths)
    while len(blocked) < required:
        best: tuple[float, float, str] | None = None
        for edge_id, raw in candidates.items():
            if edge_id in selected:
                continue
            newly_blocked = [path for path in paths_by_edge[edge_id] if path.path_id not in blocked]
            reduction = sum(path.relative_exposure for path in newly_blocked)
            if reduction <= 0:
                continue
            score = reduction / raw.business_removal_cost
            candidate = (score, -raw.business_removal_cost, edge_id)
            if best is None or candidate > best:
                best = candidate
        if best is None:
            break
        selected.add(best[2])
        blocked.update(path.path_id for path in paths_by_edge[best[2]])
    return build_verified_plan(
        problem,
        solver=SolverName.RISK_GREEDY,
        removed_edge_ids=tuple(sorted(selected)),
        target_fraction=target_fraction,
        runtime_seconds=time.perf_counter() - started,
        maximum_depth=maximum_depth,
    )
