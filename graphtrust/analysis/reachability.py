"""Critical-asset reachability summaries."""

from dataclasses import dataclass

from graphtrust.graph.protocol import CapabilityGraphBackend
from graphtrust.graph.traversal import reverse_reachable_identities


@dataclass(frozen=True, slots=True)
class SourceReachability:
    source_id: str
    reachable_critical_assets: tuple[str, ...]
    minimum_depth: int


def summarize_critical_reachability(
    backend: CapabilityGraphBackend,
    critical_asset_ids: tuple[str, ...],
    *,
    maximum_depth: int = 8,
    include_dormant: bool = False,
) -> tuple[SourceReachability, ...]:
    """Use reverse pruning, then report reachable crown jewels per source."""
    candidates = reverse_reachable_identities(
        backend,
        critical_asset_ids,
        maximum_depth=maximum_depth,
        include_dormant=include_dormant,
    )
    summaries: list[SourceReachability] = []
    critical_set = set(critical_asset_ids)
    for source_id, minimum_depth in candidates.minimum_depth_by_source.items():
        distances = backend.reachable((source_id,), maximum_depth=maximum_depth)
        reachable_assets = tuple(sorted(critical_set.intersection(distances)))
        if reachable_assets:
            summaries.append(
                SourceReachability(
                    source_id=source_id,
                    reachable_critical_assets=reachable_assets,
                    minimum_depth=minimum_depth,
                )
            )
    return tuple(summaries)
