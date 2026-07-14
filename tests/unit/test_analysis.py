"""Path scoring, bounded search, baselines, ZTRI, and explanations."""

import math
from datetime import UTC, datetime

import pytest

from graphtrust.analysis.choke_points import analyze_choke_points, rank_path_choke_points
from graphtrust.analysis.counterfactual import finding_blocked_after_removal
from graphtrust.analysis.explanations import explanation_record, render_path_explanation
from graphtrust.analysis.path_risk import (
    edge_transition_cost,
    relative_path_risk,
    start_exposure,
)
from graphtrust.analysis.paths import top_k_loopless_paths
from graphtrust.analysis.reachability import summarize_critical_reachability
from graphtrust.analysis.runner import AnalysisLimits, run_analysis_methods
from graphtrust.graph.networkx_backend import NetworkXBackend
from graphtrust.schemas.conditions import ConditionState
from graphtrust.schemas.findings import AnalysisMethod
from graphtrust.schemas.nodes import (
    Environment,
    GraphNode,
    IdentityStatus,
    NodeType,
    PrivilegeLabel,
    Provider,
)
from graphtrust.semantics.effective_access import EffectiveCapabilityEdge


def node(
    node_id: str,
    node_type: NodeType,
    *,
    privilege: PrivilegeLabel = PrivilegeLabel.LOW,
    status: IdentityStatus = IdentityStatus.NOT_APPLICABLE,
    authentication_strength: float = 0.8,
    criticality: float = 0.1,
) -> GraphNode:
    return GraphNode(
        node_id=node_id,
        node_type=node_type,
        display_name=f"Synthetic {node_id}",
        provider=Provider.GENERIC,
        tenant_id="tenant:1",
        environment=Environment.PROD,
        department="Engineering",
        criticality=criticality,
        privilege_label=privilege,
        identity_status=status,
        authentication_strength=authentication_strength,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tags_json="{}",
        generator_seed=104729,
    )


def edge(
    edge_id: str,
    source: str,
    target: str,
    *,
    capability: str = "READS",
    transition: str = "READS",
    rule: str = "direct_capability_transition",
    exploitability: float = 0.8,
    condition_state: ConditionState = ConditionState.TRUE,
    control_strength: float = 0.0,
) -> EffectiveCapabilityEdge:
    raw_id = "raw:" + edge_id
    return EffectiveCapabilityEdge(
        edge_id=edge_id,
        actor_before=source,
        actor_after=(target if transition in {"ASSUMES_ROLE", "CAN_IMPERSONATE"} else source),
        resource_or_identity_target=target,
        capability=capability,
        transition_type=transition,
        condition_state=condition_state,
        relative_exploitability=exploitability,
        control_strength=control_strength,
        business_removal_candidates=(raw_id,),
        raw_evidence_edge_ids=(raw_id,),
        semantic_rule_id=rule,
        source_provider="GENERIC",
    )


def analysis_fixture() -> tuple[tuple[GraphNode, ...], tuple[EffectiveCapabilityEdge, ...]]:
    nodes = (
        node("low", NodeType.HUMAN_IDENTITY, status=IdentityStatus.ACTIVE),
        node(
            "high",
            NodeType.HUMAN_IDENTITY,
            privilege=PrivilegeLabel.HIGH,
            status=IdentityStatus.ACTIVE,
        ),
        node("role", NodeType.ROLE),
        node("asset", NodeType.DATABASE, criticality=0.95),
    )
    edges = (
        edge("effective:direct", "low", "asset", exploitability=0.4),
        edge(
            "effective:low-role",
            "low",
            "role",
            capability="ASSUMES_ROLE",
            transition="ASSUMES_ROLE",
            rule="direct_capability_transition",
            exploitability=0.9,
        ),
        edge(
            "effective:high-role",
            "high",
            "role",
            capability="ASSUMES_ROLE",
            transition="ASSUMES_ROLE",
            rule="direct_capability_transition",
            exploitability=0.9,
        ),
        edge(
            "effective:role-asset",
            "role",
            "asset",
            capability="ADMINISTERS",
            transition="ADMINISTERS",
            rule="direct_capability_transition",
            exploitability=0.9,
        ),
    )
    return nodes, edges


def test_path_risk_formula_matches_specification() -> None:
    identity = node(
        "identity",
        NodeType.HUMAN_IDENTITY,
        status=IdentityStatus.ACTIVE,
        authentication_strength=0.8,
    )
    target = node("target", NodeType.DATABASE, criticality=0.9)
    transition = edge(
        "effective:risk",
        "identity",
        "target",
        exploitability=0.5,
        control_strength=0.25,
    )
    expected_cost = -math.log(0.5) + 0.08 + 0.40 * 0.25
    expected_exposure = 0.35 + 0.35 * 0.2
    assert edge_transition_cost(transition) == pytest.approx(expected_cost)
    assert start_exposure(identity) == pytest.approx(expected_exposure)
    assert relative_path_risk(identity, target, (transition,)) == pytest.approx(
        0.9 * expected_exposure * math.exp(-expected_cost)
    )


def test_unknown_condition_adds_declared_penalty() -> None:
    known = edge("known", "source", "target", exploitability=0.8)
    unknown = edge(
        "unknown",
        "source",
        "target",
        exploitability=0.8,
        condition_state=ConditionState.UNKNOWN,
    )
    assert edge_transition_cost(unknown) - edge_transition_cost(known) == pytest.approx(0.35)


def test_top_k_search_is_typed_deterministic_and_preserves_parallel_paths() -> None:
    source = node("source", NodeType.HUMAN_IDENTITY, status=IdentityStatus.ACTIVE)
    middle = node("middle", NodeType.ROLE)
    target = node("target", NodeType.DATABASE, criticality=0.9)
    edges = (
        edge("effective:a", "source", "middle", exploitability=0.9),
        edge("effective:b", "middle", "target", exploitability=0.9),
        edge("effective:c", "middle", "target", exploitability=0.9),
        edge("effective:direct", "source", "target", exploitability=0.3),
    )
    graph = NetworkXBackend((source, middle, target), edges)
    result = top_k_loopless_paths(graph, "source", "target", top_k=3, maximum_depth=3)
    assert [path.edge_ids for path in result.paths] == [
        ("effective:a", "effective:b"),
        ("effective:a", "effective:c"),
        ("effective:direct",),
    ]
    assert result.search_complete


def test_path_search_reports_expansion_truncation() -> None:
    nodes, edges = analysis_fixture()
    graph = NetworkXBackend(nodes, edges)
    result = top_k_loopless_paths(
        graph,
        "low",
        "asset",
        expansion_cap=0,
    )
    assert not result.search_complete
    assert result.truncation_reason == "per_source_target_expansion_cap"


def test_all_methods_share_protocol_and_keep_declared_scope() -> None:
    nodes, edges = analysis_fixture()
    results = run_analysis_methods(
        nodes,
        edges,
        ("asset",),
        limits=AnalysisLimits(
            maximum_depth=4,
            top_k_per_source_target=5,
            top_k_per_source=10,
            global_path_cap=100,
        ),
    )
    direct_sources = {item.source_identity_id for item in results[AnalysisMethod.DIRECT].findings}
    privileged_sources = {
        item.source_identity_id for item in results[AnalysisMethod.PRIVILEGED].findings
    }
    native_paths = results[AnalysisMethod.NATIVE_SCOPE].findings
    graphtrust = results[AnalysisMethod.GRAPHTRUST]

    assert direct_sources == {"low"}
    assert privileged_sources == {"high"}
    assert {item.source_identity_id for item in native_paths} == {"low"}
    assert {item.source_identity_id for item in graphtrust.findings} == {"high", "low"}
    assert all(0 <= score.ztri <= 100 for score in graphtrust.identity_scores)
    assert graphtrust.findings[0].baseline_detection
    summaries = summarize_critical_reachability(
        NetworkXBackend(nodes, edges),
        ("asset",),
        maximum_depth=4,
    )
    assert {summary.source_id for summary in summaries} == {"high", "low"}

    record = explanation_record(graphtrust.findings[0])
    assert record["ordered_path"]
    assert "potential authorization" in str(record["required_language"])
    assert "not a calibrated incident probability" in render_path_explanation(
        graphtrust.findings[0]
    )
    choke_points = rank_path_choke_points(graphtrust.findings)
    assert choke_points
    assert choke_points[0].path_count >= 1
    report = analyze_choke_points(graphtrust.findings)
    assert report.directed_dominator_nodes
    assert all(point.marginal_exposure_reduction >= 0 for point in report.edges)

    low_direct = next(
        finding
        for finding in graphtrust.findings
        if finding.source_identity_id == "low" and len(finding.path) == 1
    )
    backend = NetworkXBackend(nodes, edges)
    assert not finding_blocked_after_removal(
        backend,
        low_direct,
        ("effective:direct",),
        maximum_depth=4,
    )
    assert finding_blocked_after_removal(
        backend,
        low_direct,
        ("effective:direct", "effective:low-role"),
        maximum_depth=4,
    )
