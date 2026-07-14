"""Preregistered GraphTrust ablation definitions and score transformations."""

from dataclasses import dataclass

from graphtrust.schemas.conditions import ConditionState
from graphtrust.schemas.findings import IdentityRiskScore
from graphtrust.schemas.nodes import GraphNode, NodeType
from graphtrust.semantics.effective_access import EffectiveCapabilityEdge


@dataclass(frozen=True, slots=True)
class AblationSpec:
    name: str
    description: str


ABLATIONS = (
    AblationSpec("no_edge_typing", "Set eligible transition parameters to one common value."),
    AblationSpec("no_condition_handling", "Treat unknown conditions as known true."),
    AblationSpec("no_non_human_identities", "Exclude service, workload, and external identities."),
    AblationSpec("no_path_diversity", "Remove the path-diversity ZTRI component."),
    AblationSpec("equal_ztri_weights", "Weight all five ZTRI components equally."),
    AblationSpec("shortest_path_only", "Retain only unit-cost shortest paths."),
    AblationSpec("no_business_cost", "Use equal remediation costs."),
)


def transform_graph_for_ablation(
    name: str,
    nodes: tuple[GraphNode, ...],
    edges: tuple[EffectiveCapabilityEdge, ...],
) -> tuple[tuple[GraphNode, ...], tuple[EffectiveCapabilityEdge, ...]]:
    """Apply inference-input ablations without mutating the primary graph."""
    if name == "no_edge_typing":
        return nodes, tuple(
            edge.model_copy(update={"relative_exploitability": 0.8}) for edge in edges
        )
    if name == "no_condition_handling":
        return nodes, tuple(
            edge.model_copy(update={"condition_state": ConditionState.TRUE})
            if edge.condition_state is ConditionState.UNKNOWN
            else edge
            for edge in edges
        )
    if name == "no_non_human_identities":
        excluded = {
            node.node_id
            for node in nodes
            if node.node_type
            in {
                NodeType.SERVICE_ACCOUNT,
                NodeType.WORKLOAD_IDENTITY,
                NodeType.EXTERNAL_IDENTITY,
            }
        }
        return (
            tuple(node for node in nodes if node.node_id not in excluded),
            tuple(
                edge
                for edge in edges
                if edge.actor_before not in excluded
                and edge.resource_or_identity_target not in excluded
            ),
        )
    if name not in {spec.name for spec in ABLATIONS}:
        raise ValueError(f"Unknown ablation: {name}")
    return nodes, edges


def reweight_identity_score(score: IdentityRiskScore, name: str) -> IdentityRiskScore:
    """Apply the two score-only ablations with explicit renormalization."""
    components = (
        score.critical_reach,
        score.best_path,
        score.path_diversity,
        score.blast_radius,
        score.control_weakness,
    )
    if name == "no_path_diversity":
        weights = (0.30 / 0.85, 0.30 / 0.85, 0.0, 0.15 / 0.85, 0.10 / 0.85)
    elif name == "equal_ztri_weights":
        weights = (0.2,) * 5
    else:
        return score
    ztri = 100 * sum(
        component * weight for component, weight in zip(components, weights, strict=True)
    )
    return score.model_copy(update={"ztri": max(0.0, min(100.0, ztri))})
