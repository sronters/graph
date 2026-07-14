"""Near-optimal non-identical remediation plan enumeration."""

from graphtrust.remediation.path_hitting_set import solve_path_hitting_set
from graphtrust.remediation.problem import RemediationProblem
from graphtrust.schemas.remediation import RemediationConstraints, RemediationPlan, SolverStatus


def alternative_plans(
    problem: RemediationProblem,
    *,
    target_fraction: float = 1.0,
    constraints: RemediationConstraints | None = None,
    maximum_plans: int = 5,
    cost_tolerance: float = 0.20,
    time_limit_seconds: float = 120.0,
) -> tuple[RemediationPlan, ...]:
    """Return distinct plans within the configured modeled-cost frontier."""
    if maximum_plans < 1:
        return ()
    plans: list[RemediationPlan] = []
    forbidden: list[frozenset[str]] = []
    best_cost: float | None = None
    resolved_constraints = constraints or RemediationConstraints()
    for _ in range(maximum_plans):
        plan = solve_path_hitting_set(
            problem,
            target_fraction=target_fraction,
            constraints=resolved_constraints,
            time_limit_seconds=time_limit_seconds,
            forbidden_solutions=forbidden,
        )
        if plan.status not in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}:
            break
        if best_cost is None:
            best_cost = plan.modeled_cost
            tolerance_limit = best_cost * (1.0 + cost_tolerance)
            current_limit = resolved_constraints.maximum_cost
            resolved_constraints = resolved_constraints.model_copy(
                update={
                    "maximum_cost": (
                        min(current_limit, tolerance_limit)
                        if current_limit is not None
                        else tolerance_limit
                    )
                }
            )
        elif plan.modeled_cost > best_cost * (1.0 + cost_tolerance) + 1e-9:
            break
        plans.append(plan)
        forbidden.append(frozenset(plan.removed_edge_ids))
    return tuple(plans)
