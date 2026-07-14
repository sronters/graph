"""Scalable igraph backend with reference-compatible semantics."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable, Sequence

import igraph as ig  # type: ignore[import-untyped]

from graphtrust.graph.protocol import CapabilityPath
from graphtrust.schemas.nodes import GraphNode
from graphtrust.semantics.effective_access import EffectiveCapabilityEdge


class IgraphBackend:
    """Indexed multigraph backend for medium and large analysis."""

    def __init__(
        self,
        nodes: Sequence[GraphNode],
        edges: Sequence[EffectiveCapabilityEdge],
    ) -> None:
        self._nodes = {node.node_id: node for node in nodes}
        self._edges = {edge.edge_id: edge for edge in edges}
        self._node_ids = tuple(sorted(self._nodes))
        self._index = {node_id: index for index, node_id in enumerate(self._node_ids)}
        self._out: dict[str, list[tuple[str, EffectiveCapabilityEdge]]] = defaultdict(list)
        self._in: dict[str, list[tuple[str, EffectiveCapabilityEdge]]] = defaultdict(list)
        indexed_edges: list[tuple[int, int]] = []
        for edge in sorted(edges, key=lambda item: item.edge_id):
            if edge.actor_before not in self._nodes:
                raise ValueError(f"Unknown effective-edge source: {edge.actor_before}")
            if edge.resource_or_identity_target not in self._nodes:
                raise ValueError(
                    f"Unknown effective-edge target: {edge.resource_or_identity_target}"
                )
            target = edge.resource_or_identity_target
            self._out[edge.actor_before].append((target, edge))
            self._in[target].append((edge.actor_before, edge))
            indexed_edges.append((self._index[edge.actor_before], self._index[target]))
        for adjacency in (*self._out.values(), *self._in.values()):
            adjacency.sort(key=lambda item: (item[0], item[1].edge_id))
        self._graph = ig.Graph(n=len(nodes), edges=indexed_edges, directed=True)

    @property
    def node_count(self) -> int:
        return int(self._graph.vcount())

    @property
    def edge_count(self) -> int:
        return int(self._graph.ecount())

    def nodes(self) -> tuple[GraphNode, ...]:
        return tuple(self._nodes[node_id] for node_id in self._node_ids)

    def edges(self) -> tuple[EffectiveCapabilityEdge, ...]:
        return tuple(self._edges[edge_id] for edge_id in sorted(self._edges))

    def successors(self, node_id: str) -> tuple[tuple[str, EffectiveCapabilityEdge], ...]:
        return tuple(self._out.get(node_id, ()))

    def predecessors(self, node_id: str) -> tuple[tuple[str, EffectiveCapabilityEdge], ...]:
        return tuple(self._in.get(node_id, ()))

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
            if seed in self._nodes:
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
        if source_id not in self._nodes or target_id not in self._nodes:
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
            for next_id, edge in reversed(self.successors(node_id)):
                if next_id not in node_path:
                    stack.append((next_id, (*node_path, next_id), (*edge_path, edge)))
        return tuple(sorted(results, key=lambda path: path.edge_ids))

    def without_edges(self, edge_ids: Sequence[str]) -> IgraphBackend:
        removed = set(edge_ids)
        return IgraphBackend(
            self.nodes(),
            tuple(edge for edge in self.edges() if edge.edge_id not in removed),
        )
