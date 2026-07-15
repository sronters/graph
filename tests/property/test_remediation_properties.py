"""Property-based remediation safety invariants."""

from hypothesis import given, settings
from hypothesis import strategies as st

from graphtrust.remediation.path_hitting_set import solve_path_hitting_set
from graphtrust.remediation.problem import RemediationProblem
from tests.unit.test_remediation import remediation_problem


@settings(max_examples=12, deadline=None)
@given(
    removable_costs=st.lists(
        st.floats(min_value=0.1, max_value=20, allow_nan=False, allow_infinity=False),
        min_size=4,
        max_size=4,
    )
)
def test_protected_edges_never_appear_and_claimed_paths_are_hit(
    removable_costs: list[float],
) -> None:
    base = remediation_problem()
    updated_raw = []
    cost_index = 0
    for raw in base.raw_edges:
        if raw.protected:
            updated_raw.append(raw)
        else:
            updated_raw.append(
                raw.model_copy(update={"business_removal_cost": removable_costs[cost_index]})
            )
            cost_index += 1
    problem = RemediationProblem(
        backend=base.backend,
        raw_edges=tuple(updated_raw),
        findings=base.findings,
        requirements=base.requirements,
    )
    plan = solve_path_hitting_set(problem, maximum_depth=4)
    protected = {edge.edge_id for edge in problem.raw_edges if edge.protected}
    assert protected.isdisjoint(plan.removed_edge_ids)
    removed = set(plan.removed_edge_ids)
    path_by_id = {path.path_id: path for path in problem.dangerous_paths()}
    assert all(
        removed.intersection(path_by_id[path_id].raw_edge_ids) for path_id in plan.blocked_path_ids
    )
