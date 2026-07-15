"""Counterfactual edge-removal verification for findings."""

from collections.abc import Sequence

from graphtrust.graph.protocol import CapabilityGraphBackend
from graphtrust.schemas.findings import PathFinding


def finding_blocked_after_removal(
    backend: CapabilityGraphBackend,
    finding: PathFinding,
    removed_effective_edge_ids: Sequence[str],
    *,
    maximum_depth: int,
) -> bool:
    """Rerun reachability; never infer success from the proposed cut alone."""
    reduced = backend.without_edges(removed_effective_edge_ids)
    reachable = reduced.reachable(
        (finding.source_identity_id,),
        maximum_depth=maximum_depth,
    )
    return finding.target_asset_id not in reachable
