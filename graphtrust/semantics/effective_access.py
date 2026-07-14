"""Normalized traversal-edge schemas."""

from pydantic import Field, model_validator

from graphtrust.schemas.base import StrictModel
from graphtrust.schemas.conditions import ConditionState
from graphtrust.schemas.nodes import StableId


class EffectiveCapabilityEdge(StrictModel):
    """One evidence-preserving transition in the compiled capability graph."""

    edge_id: StableId
    actor_before: StableId
    actor_after: StableId
    resource_or_identity_target: StableId
    capability: str
    transition_type: str
    condition_state: ConditionState
    relative_exploitability: float = Field(gt=0, le=1)
    control_strength: float = Field(default=0, ge=0, le=1)
    business_removal_candidates: tuple[StableId, ...]
    raw_evidence_edge_ids: tuple[StableId, ...] = Field(min_length=1)
    semantic_rule_id: str = Field(min_length=1)
    source_provider: str

    @model_validator(mode="after")
    def removal_candidates_must_be_evidence(self) -> "EffectiveCapabilityEdge":
        unknown = set(self.business_removal_candidates) - set(self.raw_evidence_edge_ids)
        if unknown:
            raise ValueError("business removal candidates must be raw evidence edges")
        return self


class RejectedSemanticEdge(StrictModel):
    """Documented reason that raw evidence was not traversable."""

    raw_evidence_edge_ids: tuple[StableId, ...] = Field(min_length=1)
    semantic_rule_id: str
    reason: str
