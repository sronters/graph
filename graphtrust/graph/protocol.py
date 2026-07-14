"""Backend-neutral graph protocol."""

from collections.abc import Iterable, Sequence
from typing import Protocol, runtime_checkable

from pydantic import Field

from graphtrust.schemas.base import StrictModel
from graphtrust.schemas.nodes import GraphNode
from graphtrust.semantics.effective_access import EffectiveCapabilityEdge


class CapabilityPath(StrictModel):
    """Ordered node and effective-edge sequence."""

    node_ids: tuple[str, ...] = Field(min_length=2)
    edges: tuple[EffectiveCapabilityEdge, ...] = Field(min_length=1)

    @property
    def edge_ids(self) -> tuple[str, ...]:
        return tuple(edge.edge_id for edge in self.edges)


@runtime_checkable
class CapabilityGraphBackend(Protocol):
    """Minimum protocol shared by correctness and scalable backends."""

    @property
    def node_count(self) -> int: ...

    @property
    def edge_count(self) -> int: ...

    def nodes(self) -> tuple[GraphNode, ...]: ...

    def edges(self) -> tuple[EffectiveCapabilityEdge, ...]: ...

    def successors(self, node_id: str) -> tuple[tuple[str, EffectiveCapabilityEdge], ...]: ...

    def predecessors(self, node_id: str) -> tuple[tuple[str, EffectiveCapabilityEdge], ...]: ...

    def reachable(self, sources: Iterable[str], *, maximum_depth: int) -> dict[str, int]: ...

    def reverse_reachable(
        self, targets: Iterable[str], *, maximum_depth: int
    ) -> dict[str, int]: ...

    def bounded_simple_paths(
        self,
        source_id: str,
        target_id: str,
        *,
        maximum_depth: int,
        path_cap: int | None = None,
    ) -> tuple[CapabilityPath, ...]: ...

    def without_edges(self, edge_ids: Sequence[str]) -> "CapabilityGraphBackend": ...
