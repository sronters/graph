"""Shared remediation-method and target execution protocol."""

from dataclasses import dataclass

from graphtrust.remediation.constraint_generation import solve_with_constraint_generation
from graphtrust.remediation.degree_baseline import solve_degree_greedy
from graphtrust.remediation.min_cut import solve_weighted_min_cut
from graphtrust.remediation.problem import RemediationProblem
from graphtrust.remediation.risk_greedy import solve_risk_greedy
from graphtrust.schemas.remediation import RemediationConstraints, RemediationPlan, SolverName


@dataclass(frozen=True, slots=True)
class RemediationRun:
    solver: SolverName
    target_fraction: float
    plan: RemediationPlan


def run_remediation_methods(
    problem: RemediationProblem,
    *,
    solvers: tuple[SolverName, ...],
    targets: tuple[float, ...],
    constraints: RemediationConstraints | None = None,
    maximum_depth: int = 8,
) -> tuple[RemediationRun, ...]:
    """Run B4, B5, weighted cut, and constraint generation through one protocol."""
    resolved_constraints = constraints or RemediationConstraints()
    runs: list[RemediationRun] = []
    for target in targets:
        if not 0 < target <= 1:
            raise ValueError("remediation targets must be in (0, 1]")
        for solver in solvers:
            if solver is SolverName.DEGREE_GREEDY:
                plan = solve_degree_greedy(
                    problem,
                    target_fraction=target,
                    maximum_depth=maximum_depth,
                )
            elif solver is SolverName.RISK_GREEDY:
                plan = solve_risk_greedy(
                    problem,
                    target_fraction=target,
                    maximum_depth=maximum_depth,
                )
            elif solver is SolverName.MIN_CUT:
                plan = solve_weighted_min_cut(problem, maximum_depth=maximum_depth)
            else:
                plan = solve_with_constraint_generation(
                    problem,
                    target_fraction=target,
                    constraints=resolved_constraints,
                    maximum_depth=maximum_depth,
                )
            runs.append(RemediationRun(solver=solver, target_fraction=target, plan=plan))
    return tuple(runs)
