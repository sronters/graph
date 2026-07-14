"""B0 deliberately narrow direct-entitlement baseline."""

from graphtrust.schemas.edges import EdgeType
from graphtrust.semantics.effective_access import EffectiveCapabilityEdge

DIRECT_CAPABILITIES = frozenset(
    {
        EdgeType.READS.value,
        EdgeType.WRITES.value,
        EdgeType.ADMINISTERS.value,
        EdgeType.APPROVED_ACCESS.value,
        EdgeType.GRANTS_PERMISSION.value,
    }
)


def is_direct_entitlement(edge: EffectiveCapabilityEdge) -> bool:
    """Accept only one-evidence direct permissions, excluding transitions and inheritance."""
    return (
        edge.semantic_rule_id == "direct_capability_transition"
        and edge.capability in DIRECT_CAPABILITIES
        and len(edge.raw_evidence_edge_ids) == 1
    )
