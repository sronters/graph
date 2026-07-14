"""Auditable relative path-risk model from the research specification."""

import math
from collections.abc import Sequence

from graphtrust.schemas.conditions import ConditionState
from graphtrust.schemas.nodes import GraphNode, IdentityStatus, NodeType
from graphtrust.semantics.effective_access import EffectiveCapabilityEdge

LENGTH_PENALTY = 0.08
UNKNOWN_PENALTY = 0.35
CONTROL_STRENGTH_PENALTY = 0.40


def start_exposure(identity: GraphNode) -> float:
    """Calculate deterministic starting-identity exposure in [0, 1]."""
    dormant = 1.0 if identity.identity_status is IdentityStatus.DORMANT else 0.0
    external = 1.0 if identity.node_type is NodeType.EXTERNAL_IDENTITY else 0.0
    value = (
        0.35 + 0.35 * (1.0 - identity.authentication_strength) + 0.20 * dormant + 0.10 * external
    )
    return max(0.0, min(1.0, value))


def edge_transition_cost(edge: EffectiveCapabilityEdge) -> float:
    """Return the additive ordinal cost of one normalized transition."""
    unknown = 1.0 if edge.condition_state is ConditionState.UNKNOWN else 0.0
    return (
        -math.log(edge.relative_exploitability)
        + LENGTH_PENALTY
        + UNKNOWN_PENALTY * unknown
        + CONTROL_STRENGTH_PENALTY * edge.control_strength
    )


def path_transition_cost(edges: Sequence[EffectiveCapabilityEdge]) -> float:
    return sum(edge_transition_cost(edge) for edge in edges)


def relative_path_risk(
    identity: GraphNode,
    target: GraphNode,
    edges: Sequence[EffectiveCapabilityEdge],
) -> float:
    """Rank one authorization path; this is not an incident probability."""
    value = target.criticality * start_exposure(identity) * math.exp(-path_transition_cost(edges))
    return max(0.0, min(1.0, value))
