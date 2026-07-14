"""NetworkX correctness backend preserving directed parallel edges."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Sequence

import networkx as nx

from graphtrust.graph.protocol import CapabilityPath
from graphtrust.schemas.nodes import GraphNode
from graphtrust.semantics.effective_access import EffectiveCapabilityEdge


class NetworkXBackend:
    """Reference multigraph backend used for fixtures and parity checks."""

    def __init__(
        self,
        nodes: Sequence[GraphNode],
        edges: Sequence[EffectiveCapabilityEdge],
    ) -> None:
        self._nodes = {node.node_id: node for node in nodes}
        self._edges = {edge.edge_id: edge for edge in edges}
        self._graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()
        for node in sorted(nodes, key=lambda item: item.node_id):
            self._graph.add_node(node.node_id)
        for edge in sorted(edges, key=lambda item: item.edge_id):
            if edge.actor_before not in self._nodes:
                raise ValueError(f"Unknown effective-edge source: {edge.actor_before}")
            if edge.resource_or_identity_target not in self._nodes:
                raise ValueError(
                    f"Unknown effective-edge target: {edge.resource_or_identity_target}"
                )
            self._graph.add_edge(
                edge.actor_before,
                edge.resource_or_identity_target,
                key=edge.edge_id,
            )

    @property
    def node_count(self) -> int:
        return self._graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._graph.number_of_edges()

    def nodes(self) -> tuple[GraphNode, ...]:
        return tuple(self._nodes[node_id] for node_id in sorted(self._nodes))

    def edges(self) -> tuple[EffectiveCapabilityEdge, ...]:
        return tuple(self._edges[edge_id] for edge_id in sorted(self._edges))

    def successors(self, node_id: str) -> tuple[tuple[str, EffectiveCapabilityEdge], ...]:
        if node_id not in self._graph:
            return ()
        values = [
            (target, self._edges[edge_id])
            for _, target, edge_id in self._graph.out_edges(node_id, keys=True)
        ]
        return tuple(sorted(values, key=lambda item: (item[0], item[1].edge_id)))

    def predecessors(self, node_id: str) -> tuple[tuple[str, EffectiveCapabilityEdge], ...]:
        if node_id not in self._graph:
            return ()
        values = [
            (source, self._edges[edge_id])
            for source, _, edge_id in self._graph.in_edges(node_id, keys=True)
        ]
        return tuple(sorted(values, key=lambda item: (item[0], item[1].edge_id)))

    def _distances(
        self,
        seeds: Iterable[str],
        *,
        maximum_depth: int,
        reverse: bool,
    ) -> dict[str, int]:
        distances: dict[str, int] = {}
        queue: deque[tuple[str, int]] = deque()
        for seed in sorted(set(seeds)):
            if seed in self._graph:
                distances[seed] = 0
                queue.append((seed, 0))
        while queue:
            node_id, depth = queue.popleft()
            if depth >= maximum_depth:
                continue
            adjacent = self.predecessors(node_id) if reverse else self.successors(node_id)
            for adjacent_id, _ in adjacent:
                next_depth = depth + 1
                if next_depth < distances.get(adjacent_id, maximum_depth + 1):
                    distances[adjacent_id] = next_depth
                    queue.append((adjacent_id, next_depth))
        return dict(sorted(distances.items()))

    def reachable(self, sources: Iterable[str], *, maximum_depth: int) -> dict[str, int]:
        return self._distances(sources, maximum_depth=maximum_depth, reverse=False)

    def reverse_reachable(self, targets: Iterable[str], *, maximum_depth: int) -> dict[str, int]:
        return self._distances(targets, maximum_depth=maximum_depth, reverse=True)

    def bounded_simple_paths(
        self,
        source_id: str,
        target_id: str,
        *,
        maximum_depth: int,
        path_cap: int | None = None,
    ) -> tuple[CapabilityPath, ...]:
        if source_id not in self._graph or target_id not in self._graph:
            return ()
        results: list[CapabilityPath] = []
        stack: list[tuple[str, tuple[str, ...], tuple[EffectiveCapabilityEdge, ...]]] = [
            (source_id, (source_id,), ())
        ]
        while stack:
            node_id, node_path, edge_path = stack.pop()
            if node_id == target_id and edge_path:
                results.append(CapabilityPath(node_ids=node_path, edges=edge_path))
                if path_cap is not None and len(results) >= path_cap:
                    break
                continue
            if len(edge_path) >= maximum_depth:
                continue
            successors = self.successors(node_id)
            for next_id, edge in reversed(successors):
                if next_id not in node_path:
                    stack.append((next_id, (*node_path, next_id), (*edge_path, edge)))
        return tuple(sorted(results, key=lambda path: path.edge_ids))

    def without_edges(self, edge_ids: Sequence[str]) -> NetworkXBackend:
        removed = set(edge_ids)
        return NetworkXBackend(
            self.nodes(),
            tuple(edge for edge in self.edges() if edge.edge_id not in removed),
        )
