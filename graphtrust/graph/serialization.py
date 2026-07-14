"""Stable JSON serialization for backend parity and artifact exchange."""

import json
from collections.abc import Sequence

from graphtrust.schemas.nodes import GraphNode
from graphtrust.semantics.effective_access import EffectiveCapabilityEdge


def serialize_graph(nodes: Sequence[GraphNode], edges: Sequence[EffectiveCapabilityEdge]) -> bytes:
    """Serialize records in canonical ID order."""
    payload = {
        "schema_version": "1.0",
        "nodes": [
            node.model_dump(mode="json") for node in sorted(nodes, key=lambda item: item.node_id)
        ],
        "edges": [
            edge.model_dump(mode="json") for edge in sorted(edges, key=lambda item: item.edge_id)
        ],
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def deserialize_graph(
    value: bytes,
) -> tuple[tuple[GraphNode, ...], tuple[EffectiveCapabilityEdge, ...]]:
    """Validate serialized graph records before backend construction."""
    payload = json.loads(value)
    if payload.get("schema_version") != "1.0":
        raise ValueError("Unsupported graph serialization schema")
    nodes = tuple(GraphNode.model_validate(item) for item in payload["nodes"])
    edges = tuple(EffectiveCapabilityEdge.model_validate(item) for item in payload["edges"])
    return nodes, edges
