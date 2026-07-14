"""B3 native-scope effective-access baseline edge filter."""

from graphtrust.semantics.effective_access import EffectiveCapabilityEdge

EXCLUDED_TRANSITIONS = frozenset(
    {
        "ASSUMES_ROLE",
        "CAN_IMPERSONATE",
        "CAN_MODIFY",
        "CAN_CREATE_CREDENTIAL",
        "CAN_TRIGGER",
        "RUNS_AS",
        "DEPLOYS_TO",
        "FEDERATES_TO",
    }
)


def is_native_scope_edge(edge: EffectiveCapabilityEdge) -> bool:
    """Retain direct/group/scope access but exclude identity-control chains."""
    return edge.transition_type not in EXCLUDED_TRANSITIONS
