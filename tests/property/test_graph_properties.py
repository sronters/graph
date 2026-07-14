"""Graph monotonicity and serialization invariants."""

from datetime import UTC, datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from graphtrust.graph.igraph_backend import IgraphBackend
from graphtrust.graph.networkx_backend import NetworkXBackend
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


def graph_node(index: int) -> GraphNode:
    return GraphNode(
        node_id=f"node:{index}",
        node_type=NodeType.HUMAN_IDENTITY if index == 0 else NodeType.APPLICATION,
        display_name=f"Synthetic node {index}",
        provider=Provider.GENERIC,
        tenant_id="tenant:1",
        environment=Environment.DEV,
        department="Engineering",
        criticality=0,
        privilege_label=PrivilegeLabel.NONE,
        identity_status=IdentityStatus.ACTIVE if index == 0 else IdentityStatus.NOT_APPLICABLE,
        authentication_strength=0.8,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tags_json="{}",
        generator_seed=104729,
    )


def graph_edge(index: int, source: int, target: int) -> EffectiveCapabilityEdge:
    raw_id = f"raw:{index}"
    return EffectiveCapabilityEdge(
        edge_id=f"effective:{index}",
        actor_before=f"node:{source}",
        actor_after=f"node:{source}",
        resource_or_identity_target=f"node:{target}",
        capability="FIXTURE",
        transition_type="FIXTURE",
        condition_state=ConditionState.TRUE,
        relative_exploitability=0.8,
        business_removal_candidates=(raw_id,),
        raw_evidence_edge_ids=(raw_id,),
        semantic_rule_id="property_fixture",
        source_provider="GENERIC",
    )


@settings(max_examples=50, deadline=None)
@given(
    edge_pairs=st.lists(
        st.tuples(st.integers(0, 5), st.integers(0, 5)).filter(lambda pair: pair[0] != pair[1]),
        min_size=0,
        max_size=12,
        unique=True,
    ),
    removal_indexes=st.sets(st.integers(0, 11), max_size=6),
)
def test_removing_edges_cannot_increase_reachability(
    edge_pairs: list[tuple[int, int]],
    removal_indexes: set[int],
) -> None:
    nodes = tuple(graph_node(index) for index in range(6))
    edges = tuple(
        graph_edge(index, source, target) for index, (source, target) in enumerate(edge_pairs)
    )
    graph = NetworkXBackend(nodes, edges)
    removed_ids = tuple(f"effective:{index}" for index in removal_indexes)
    reduced = graph.without_edges(removed_ids)
    original_reachable = set(graph.reachable(("node:0",), maximum_depth=6))
    reduced_reachable = set(reduced.reachable(("node:0",), maximum_depth=6))
    assert reduced_reachable <= original_reachable


@settings(max_examples=40, deadline=None)
@given(
    edge_pairs=st.lists(
        st.tuples(st.integers(0, 5), st.integers(0, 5)).filter(lambda pair: pair[0] != pair[1]),
        min_size=0,
        max_size=12,
        unique=True,
    )
)
def test_networkx_and_igraph_reachable_pairs_are_identical(
    edge_pairs: list[tuple[int, int]],
) -> None:
    nodes = tuple(graph_node(index) for index in range(6))
    edges = tuple(
        graph_edge(index, source, target) for index, (source, target) in enumerate(edge_pairs)
    )
    reference = NetworkXBackend(nodes, edges)
    scalable = IgraphBackend(nodes, edges)
    for source_index in range(6):
        source = f"node:{source_index}"
        assert scalable.reachable((source,), maximum_depth=6) == reference.reachable(
            (source,), maximum_depth=6
        )
    reference_paths = reference.bounded_simple_paths(
        "node:0", "node:5", maximum_depth=5, path_cap=50
    )
    scalable_paths = scalable.bounded_simple_paths("node:0", "node:5", maximum_depth=5, path_cap=50)
    assert [path.edge_ids for path in scalable_paths] == [path.edge_ids for path in reference_paths]
    assert scalable.edge_count == reference.edge_count
    assert scalable.node_count == reference.node_count
