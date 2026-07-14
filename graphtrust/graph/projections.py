"""Loss-aware projections for structural diagnostics."""

from __future__ import annotations

from collections.abc import Sequence

import networkx as nx

from graphtrust.semantics.effective_access import EffectiveCapabilityEdge


def simple_risk_projection(edges: Sequence[EffectiveCapabilityEdge]) -> nx.DiGraph[str]:
    """Aggregate parallel transitions while retaining every effective edge ID."""
    graph: nx.DiGraph[str] = nx.DiGraph()
    grouped: dict[tuple[str, str], list[EffectiveCapabilityEdge]] = {}
    for edge in edges:
        key = (edge.actor_before, edge.resource_or_identity_target)
        grouped.setdefault(key, []).append(edge)
    for (source, target), parallel in sorted(grouped.items()):
        graph.add_edge(
            source,
            target,
            effective_edge_ids=tuple(sorted(edge.edge_id for edge in parallel)),
            maximum_relative_exploitability=max(edge.relative_exploitability for edge in parallel),
            evidence_edge_ids=tuple(
                sorted({raw_id for edge in parallel for raw_id in edge.raw_evidence_edge_ids})
            ),
        )
    return graph
