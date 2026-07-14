"""Backend-neutral candidate-source and fixture path traversal."""

from dataclasses import dataclass

from graphtrust.graph.protocol import CapabilityGraphBackend, CapabilityPath
from graphtrust.schemas.nodes import IdentityStatus, NodeType

IDENTITY_TYPES = frozenset(
    {
        NodeType.HUMAN_IDENTITY,
        NodeType.SERVICE_ACCOUNT,
        NodeType.WORKLOAD_IDENTITY,
        NodeType.EXTERNAL_IDENTITY,
    }
)


@dataclass(frozen=True, slots=True)
class ReachabilityResult:
    """Candidate identities and minimum distance from a target set."""

    minimum_depth_by_source: dict[str, int]
    target_ids: tuple[str, ...]
    maximum_depth: int


def reverse_reachable_identities(
    backend: CapabilityGraphBackend,
    target_ids: tuple[str, ...],
    *,
    maximum_depth: int = 8,
    include_dormant: bool = False,
    include_disabled: bool = False,
) -> ReachabilityResult:
    """Prune the search space by reversing traversal from critical assets."""
    distances = backend.reverse_reachable(target_ids, maximum_depth=maximum_depth)
    eligible: dict[str, int] = {}
    for node in backend.nodes():
        if node.node_type not in IDENTITY_TYPES or node.node_id not in distances:
            continue
        if node.identity_status is IdentityStatus.DISABLED and not include_disabled:
            continue
        if node.identity_status is IdentityStatus.DORMANT and not include_dormant:
            continue
        eligible[node.node_id] = distances[node.node_id]
    return ReachabilityResult(
        minimum_depth_by_source=dict(sorted(eligible.items())),
        target_ids=tuple(sorted(target_ids)),
        maximum_depth=maximum_depth,
    )


def exhaustive_fixture_paths(
    backend: CapabilityGraphBackend,
    source_id: str,
    target_id: str,
    *,
    maximum_depth: int = 8,
) -> tuple[CapabilityPath, ...]:
    """Exhaustively enumerate bounded simple paths for small correctness fixtures only."""
    return backend.bounded_simple_paths(
        source_id,
        target_id,
        maximum_depth=maximum_depth,
    )
