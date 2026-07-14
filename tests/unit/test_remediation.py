"""Remediation solver optimality, protection, and verification tests."""

import itertools

import pytest

from graphtrust.analysis.runner import AnalysisLimits, run_analysis_methods
from graphtrust.graph.networkx_backend import NetworkXBackend
from graphtrust.remediation.alternatives import alternative_plans
from graphtrust.remediation.constraint_generation import solve_with_constraint_generation
from graphtrust.remediation.degree_baseline import solve_degree_greedy
from graphtrust.remediation.min_cut import solve_weighted_min_cut
from graphtrust.remediation.path_hitting_set import solve_path_hitting_set
from graphtrust.remediation.problem import RemediationProblem
from graphtrust.remediation.risk_greedy import solve_risk_greedy
from graphtrust.remediation.runner import run_remediation_methods
from graphtrust.remediation.verification import verify_source_target_reachability
from graphtrust.schemas.edges import EdgeEffect, EdgeType, GraphEdge
from graphtrust.schemas.findings import AnalysisMethod
from graphtrust.schemas.nodes import (
    IdentityStatus,
    NodeType,
    PrivilegeLabel,
    Provider,
)
from graphtrust.schemas.remediation import (
    BusinessRequirement,
    RemediationConstraints,
    SolverName,
    SolverStatus,
)
from tests.unit.test_analysis import analysis_fixture, edge, node


def raw_edge(
    edge_id: str,
    source: str,
    target: str,
    edge_type: EdgeType,
    cost: float,
    *,
    protected: bool = False,
) -> GraphEdge:
    return GraphEdge(
        edge_id=edge_id,
        source_id=source,
        target_id=target,
        edge_type=edge_type,
        provider=Provider.GENERIC,
        effect=EdgeEffect.ALLOW,
        relative_exploitability=0.8,
        business_removal_cost=cost,
        removable=not protected,
        protected=protected,
        source_artifact="remediation-fixture",
    )


def remediation_problem(*, findings_only_direct_low: bool = False) -> RemediationProblem:
    base_nodes, base_edges = analysis_fixture()
    operator = node(
        "operator",
        NodeType.HUMAN_IDENTITY,
        privilege=PrivilegeLabel.HIGH,
        status=IdentityStatus.ACTIVE,
    )
    safe = node("safe", NodeType.APPLICATION, criticality=0.4)
    business_effective = edge(
        "effective:business",
        "operator",
        "safe",
        capability="READS",
        transition="READS",
        exploitability=0.5,
    )
    nodes = (*base_nodes, operator, safe)
    effective_edges = (*base_edges, business_effective)
    backend = NetworkXBackend(nodes, effective_edges)
    findings = run_analysis_methods(
        nodes,
        effective_edges,
        ("asset",),
        methods=(AnalysisMethod.GRAPHTRUST,),
        limits=AnalysisLimits(
            maximum_depth=4,
            top_k_per_source_target=10,
            top_k_per_source=10,
            global_path_cap=100,
        ),
    )[AnalysisMethod.GRAPHTRUST].findings
    if findings_only_direct_low:
        findings = tuple(
            finding
            for finding in findings
            if finding.source_identity_id == "low" and len(finding.path) == 1
        )
    raw_edges = (
        raw_edge("raw:effective:direct", "low", "asset", EdgeType.READS, 1.0),
        raw_edge(
            "raw:effective:low-role",
            "low",
            "role",
            EdgeType.ASSUMES_ROLE,
            1.6,
        ),
        raw_edge(
            "raw:effective:high-role",
            "high",
            "role",
            EdgeType.ASSUMES_ROLE,
            1.6,
        ),
        raw_edge(
            "raw:effective:role-asset",
            "role",
            "asset",
            EdgeType.ADMINISTERS,
            3.0,
        ),
        raw_edge(
            "raw:effective:business",
            "operator",
            "safe",
            EdgeType.READS,
            10.0,
            protected=True,
        ),
    )
    requirement = BusinessRequirement(
        requirement_id="requirement:business",
        source_set=frozenset({"operator"}),
        target_set=frozenset({"safe"}),
        required_capability="READS",
        minimum_remaining_paths=1,
        maximum_path_length=2,
        priority=100,
    )
    return RemediationProblem(
        backend=backend,
        raw_edges=raw_edges,
        findings=findings,
        requirements=(requirement,),
    )


def brute_force_optimum(problem: RemediationProblem) -> float:
    candidates = tuple(problem.removable_edges())
    costs = problem.raw_edge_by_id
    best = float("inf")
    for count in range(len(candidates) + 1):
        for subset in itertools.combinations(candidates, count):
            if verify_source_target_reachability(problem, subset, maximum_depth=4).verified:
                best = min(best, sum(costs[edge_id].business_removal_cost for edge_id in subset))
    return best


def test_min_cut_and_cp_sat_match_brute_force_optimum() -> None:
    problem = remediation_problem()
    optimum = brute_force_optimum(problem)
    min_cut = solve_weighted_min_cut(problem, maximum_depth=4)
    exact = solve_path_hitting_set(problem, maximum_depth=4)
    assert optimum == pytest.approx(4.0)
    assert min_cut.modeled_cost == pytest.approx(optimum)
    assert exact.modeled_cost == pytest.approx(optimum)
    assert min_cut.counterfactual_verified
    assert exact.counterfactual_verified
    assert min_cut.protected_workflows_preserved
    assert exact.protected_workflows_preserved
    assert "raw:effective:business" not in min_cut.removed_edge_ids
    assert "raw:effective:business" not in exact.removed_edge_ids


def test_cp_sat_enforces_change_and_department_constraints() -> None:
    problem = remediation_problem()
    infeasible = solve_path_hitting_set(
        problem,
        constraints=RemediationConstraints(maximum_changes=1),
        maximum_depth=4,
    )
    assert infeasible.status is SolverStatus.INFEASIBLE
    department_limited = solve_path_hitting_set(
        problem,
        constraints=RemediationConstraints(maximum_changes_by_department={"Engineering": 0}),
        maximum_depth=4,
    )
    assert department_limited.status is SolverStatus.INFEASIBLE


def test_partial_target_and_greedy_baselines_report_verified_scope() -> None:
    problem = remediation_problem()
    partial = solve_path_hitting_set(
        problem,
        target_fraction=0.66,
        maximum_depth=4,
    )
    assert len(partial.blocked_path_ids) >= 2
    assert partial.counterfactual_verified

    degree = solve_degree_greedy(problem, target_fraction=1.0, maximum_depth=4)
    risk = solve_risk_greedy(problem, target_fraction=1.0, maximum_depth=4)
    assert degree.counterfactual_verified
    assert risk.counterfactual_verified
    assert degree.protected_workflows_preserved
    assert risk.protected_workflows_preserved


def test_constraint_generation_finds_path_omitted_from_initial_findings() -> None:
    problem = remediation_problem(findings_only_direct_low=True)
    initial = solve_path_hitting_set(problem, maximum_depth=4)
    assert not initial.counterfactual_verified
    generated = solve_with_constraint_generation(
        problem,
        maximum_depth=4,
        iteration_cap=10,
    )
    assert generated.counterfactual_verified
    assert generated.added_constraints >= 1
    assert generated.iterations >= 2


def test_alternative_plans_are_distinct_and_near_optimal() -> None:
    problem = remediation_problem()
    plans = alternative_plans(
        problem,
        maximum_plans=3,
        cost_tolerance=0.20,
    )
    assert len(plans) >= 2
    assert len({plan.removed_edge_ids for plan in plans}) == len(plans)
    assert all(plan.modeled_cost <= plans[0].modeled_cost * 1.20 for plan in plans)
    assert all("raw:effective:business" not in plan.removed_edge_ids for plan in plans)


def test_all_remediation_methods_share_target_protocol() -> None:
    runs = run_remediation_methods(
        remediation_problem(),
        solvers=tuple(SolverName),
        targets=(0.8,),
        maximum_depth=4,
    )
    assert {run.solver for run in runs} == set(SolverName)
    assert all(run.target_fraction == 0.8 for run in runs)
    assert all(run.plan.protected_workflows_preserved for run in runs)
