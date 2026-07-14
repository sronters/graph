"""Reference backend direction, multiedge, projection, and serialization tests."""

from datetime import UTC, datetime

from graphtrust.graph.networkx_backend import NetworkXBackend
from graphtrust.graph.projections import simple_risk_projection
from graphtrust.graph.serialization import deserialize_graph, serialize_graph
from graphtrust.graph.traversal import reverse_reachable_identities
from graphtrust.schemas.conditions import ConditionState
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
    status: IdentityStatus = IdentityStatus.NOT_APPLICABLE,
) -> GraphNode:
    return GraphNode(
        node_id=node_id,
        node_type=node_type,
        display_name=f"Synthetic {node_id}",
        provider=Provider.GENERIC,
        tenant_id="tenant:1",
        environment=Environment.PROD,
        department="Engineering",
        criticality=0.95 if node_type is NodeType.DATABASE else 0.1,
        privilege_label=PrivilegeLabel.LOW,
        identity_status=status,
        authentication_strength=0.8,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tags_json="{}",
        generator_seed=104729,
    )


def effective(edge_id: str, source: str, target: str, raw_id: str) -> EffectiveCapabilityEdge:
    return EffectiveCapabilityEdge(
        edge_id=edge_id,
        actor_before=source,
        actor_after=source,
        resource_or_identity_target=target,
        capability="READS",
        transition_type="FIXTURE",
        condition_state=ConditionState.TRUE,
        relative_exploitability=0.8,
        business_removal_candidates=(raw_id,),
        raw_evidence_edge_ids=(raw_id,),
        semantic_rule_id="fixture_rule",
        source_provider="GENERIC",
    )


def backend() -> NetworkXBackend:
    nodes = (
        node("human", NodeType.HUMAN_IDENTITY, IdentityStatus.ACTIVE),
        node("dormant", NodeType.HUMAN_IDENTITY, IdentityStatus.DORMANT),
        node("role", NodeType.ROLE),
        node("database", NodeType.DATABASE),
    )
    edges = (
        effective("effective:1", "human", "role", "raw:1"),
        effective("effective:2", "role", "database", "raw:2"),
        effective("effective:3", "role", "database", "raw:3"),
        effective("effective:4", "dormant", "role", "raw:4"),
    )
    return NetworkXBackend(nodes, edges)


def test_backend_preserves_parallel_edges_and_deterministic_paths() -> None:
    graph = backend()
    paths = graph.bounded_simple_paths("human", "database", maximum_depth=3)
    assert graph.node_count == 4
    assert graph.edge_count == 4
    assert [path.edge_ids for path in paths] == [
        ("effective:1", "effective:2"),
        ("effective:1", "effective:3"),
    ]


def test_direction_and_reverse_reachability_are_distinct() -> None:
    graph = backend()
    assert graph.reachable(("human",), maximum_depth=3)["database"] == 2
    assert "human" not in graph.reachable(("database",), maximum_depth=3)
    assert graph.reverse_reachable(("database",), maximum_depth=3)["human"] == 2


def test_removal_cannot_leave_a_removed_path() -> None:
    graph = backend().without_edges(("effective:1",))
    assert graph.bounded_simple_paths("human", "database", maximum_depth=3) == ()


def test_candidate_identity_filter_separates_dormant_view() -> None:
    graph = backend()
    primary = reverse_reachable_identities(graph, ("database",), maximum_depth=3)
    sensitivity = reverse_reachable_identities(
        graph,
        ("database",),
        maximum_depth=3,
        include_dormant=True,
    )
    assert set(primary.minimum_depth_by_source) == {"human"}
    assert set(sensitivity.minimum_depth_by_source) == {"dormant", "human"}


def test_projection_retains_parallel_edge_and_raw_provenance() -> None:
    projection = simple_risk_projection(backend().edges())
    attributes = projection["role"]["database"]
    assert attributes["effective_edge_ids"] == ("effective:2", "effective:3")
    assert attributes["evidence_edge_ids"] == ("raw:2", "raw:3")


def test_serialization_is_stable_and_round_trips() -> None:
    graph = backend()
    serialized = serialize_graph(graph.nodes(), graph.edges())
    reversed_serialized = serialize_graph(
        tuple(reversed(graph.nodes())), tuple(reversed(graph.edges()))
    )
    nodes, edges = deserialize_graph(serialized)
    restored = NetworkXBackend(nodes, edges)
    assert serialized == reversed_serialized
    assert restored.edges() == graph.edges()
    assert restored.nodes() == graph.nodes()
