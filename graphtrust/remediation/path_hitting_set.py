"""Exact CP-SAT constrained dangerous-path hitting set."""

import math
import time
from collections import defaultdict
from collections.abc import Sequence

from ortools.sat.python import cp_model

from graphtrust.remediation.business_constraints import verify_business_requirements
from graphtrust.remediation.problem import DangerousPath, RemediationProblem, stable_plan_id
from graphtrust.remediation.verification import (
    blocked_finding_ids,
    exposure_reduction,
    verify_source_target_reachability,
)
from graphtrust.schemas.remediation import (
    RemediationConstraints,
    RemediationPlan,
    SolverName,
    SolverStatus,
)

COST_SCALE = 1_000


def _solver_status(status: cp_model.CpSolverStatus) -> SolverStatus:
    if status == cp_model.OPTIMAL:
        return SolverStatus.OPTIMAL
    if status == cp_model.FEASIBLE:
        return SolverStatus.FEASIBLE
    if status == cp_model.INFEASIBLE:
        return SolverStatus.INFEASIBLE
    return SolverStatus.TIME_LIMIT


def solve_path_hitting_set(
    problem: RemediationProblem,
    *,
    target_fraction: float = 1.0,
    constraints: RemediationConstraints | None = None,
    time_limit_seconds: float = 120.0,
    additional_paths: Sequence[DangerousPath] = (),
    forbidden_solutions: Sequence[frozenset[str]] = (),
    solver_name: SolverName = SolverName.CONSTRAINT_GENERATION,
    maximum_depth: int = 8,
) -> RemediationPlan:
    """Minimize modeled cost subject to path, protection, and change constraints."""
    if not 0 < target_fraction <= 1:
        raise ValueError("target_fraction must be in (0, 1]")
    started = time.perf_counter()
    resolved_constraints = constraints or RemediationConstraints()
    removable = problem.removable_edges()
    model = cp_model.CpModel()
    variables = {edge_id: model.new_bool_var(f"remove:{edge_id}") for edge_id in sorted(removable)}
    paths = (*problem.dangerous_paths(), *additional_paths)
    blocked_variables: list[cp_model.IntVar] = []
    for path in paths:
        candidates = [
            variables[edge_id] for edge_id in sorted(path.raw_edge_ids) if edge_id in variables
        ]
        blocked = model.new_bool_var(f"blocked:{path.path_id}")
        blocked_variables.append(blocked)
        if not candidates:
            model.add(blocked == 0)
            continue
        model.add(sum(candidates) >= blocked)
        for candidate in candidates:
            model.add(blocked >= candidate)
    required_blocked = math.ceil(target_fraction * len(paths))
    if blocked_variables:
        model.add(sum(blocked_variables) >= required_blocked)
    elif required_blocked:
        model.add_bool_or([])

    if resolved_constraints.maximum_changes is not None:
        model.add(sum(variables.values()) <= resolved_constraints.maximum_changes)
    scaled_costs = {
        edge_id: round(edge.business_removal_cost * COST_SCALE)
        for edge_id, edge in removable.items()
    }
    if resolved_constraints.maximum_cost is not None:
        model.add(
            sum(scaled_costs[edge_id] * variable for edge_id, variable in variables.items())
            <= round(resolved_constraints.maximum_cost * COST_SCALE)
        )

    by_department: dict[str, list[cp_model.IntVar]] = defaultdict(list)
    by_provider: dict[str, list[cp_model.IntVar]] = defaultdict(list)
    node_by_id = problem.node_by_id
    for edge_id, variable in variables.items():
        raw = removable[edge_id]
        department = (
            node_by_id[raw.source_id].department if raw.source_id in node_by_id else "SYSTEM"
        )
        by_department[department].append(variable)
        by_provider[raw.provider.value].append(variable)
    for department, maximum in resolved_constraints.maximum_changes_by_department.items():
        model.add(sum(by_department.get(department, ())) <= maximum)
    for provider, maximum in resolved_constraints.maximum_changes_by_provider.items():
        model.add(sum(by_provider.get(provider, ())) <= maximum)

    for forbidden in forbidden_solutions:
        difference_terms = [
            (1 - variable) if edge_id in forbidden else variable
            for edge_id, variable in variables.items()
        ]
        if difference_terms:
            model.add(sum(difference_terms) >= 1)

    change_penalty = round(0.05 * COST_SCALE)
    objective = sum(
        (scaled_costs[edge_id] + change_penalty) * variable
        for edge_id, variable in variables.items()
    )
    model.minimize(objective)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    raw_status = solver.solve(model)
    status = _solver_status(raw_status)
    removed = (
        tuple(sorted(edge_id for edge_id, variable in variables.items() if solver.value(variable)))
        if status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}
        else ()
    )
    business = verify_business_requirements(problem, removed)
    blocked_ids = blocked_finding_ids(problem, removed)
    blocked_fraction = len(blocked_ids) / len(problem.findings) if problem.findings else 1.0
    reachability = verify_source_target_reachability(
        problem,
        removed,
        maximum_depth=maximum_depth,
    )
    target_verified = (
        reachability.verified if target_fraction == 1.0 else blocked_fraction >= target_fraction
    )
    verified = (
        status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}
        and target_verified
        and business.valid
    )
    modeled_cost = sum(removable[edge_id].business_removal_cost for edge_id in removed)
    affected = tuple(
        sorted(
            {
                node_by_id[removable[edge_id].source_id].department
                for edge_id in removed
                if removable[edge_id].source_id in node_by_id
            }
        )
    )
    objective_value = (
        solver.objective_value / COST_SCALE
        if status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}
        else None
    )
    bound = (
        solver.best_objective_bound / COST_SCALE
        if status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE, SolverStatus.TIME_LIMIT}
        else None
    )
    gap = (
        max(0.0, (objective_value - bound) / max(abs(objective_value), 1e-9))
        if objective_value is not None and bound is not None
        else None
    )
    return RemediationPlan(
        plan_id=stable_plan_id(solver_name.value, removed),
        solver=solver_name,
        status=status,
        removed_edge_ids=removed,
        modeled_cost=modeled_cost,
        blocked_path_ids=blocked_ids,
        residual_exposure=max(0.0, 1.0 - exposure_reduction(problem, removed)),
        affected_departments=affected,
        protected_workflows_preserved=business.valid,
        counterfactual_verified=verified,
        optimality_bound=bound,
        optimality_gap=gap,
        runtime_seconds=time.perf_counter() - started,
    )
