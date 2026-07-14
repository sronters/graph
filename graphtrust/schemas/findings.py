"""Structured analysis findings and path-search metadata."""

from enum import StrEnum

from pydantic import Field

from graphtrust.schemas.base import StrictModel
from graphtrust.schemas.conditions import ConditionState
from graphtrust.schemas.nodes import PrivilegeLabel, StableId


class AnalysisMethod(StrEnum):
    DIRECT = "direct"
    PRIVILEGED = "privileged"
    UNTYPED = "untyped"
    NATIVE_SCOPE = "native_scope"
    GRAPHTRUST = "graphtrust"


class PathStep(StrictModel):
    position: int = Field(ge=0)
    actor_before: StableId
    actor_after: StableId
    target_id: StableId
    capability: str
    transition_type: str
    condition_state: ConditionState
    relative_exploitability: float = Field(gt=0, le=1)
    raw_evidence_edge_ids: tuple[StableId, ...] = Field(min_length=1)
    semantic_rule_id: str


class SearchMetadata(StrictModel):
    search_complete: bool
    truncation_reason: str | None = None
    expanded_states: int = Field(ge=0)
    candidate_paths_considered: int = Field(ge=0)


class RiskComponents(StrictModel):
    criticality: float = Field(ge=0, le=1)
    start_exposure: float = Field(ge=0, le=1)
    transition_cost: float = Field(ge=0)
    path_risk: float = Field(ge=0, le=1)


class PathFinding(StrictModel):
    finding_id: StableId
    method: AnalysisMethod
    source_identity_id: StableId
    source_privilege_label: PrivilegeLabel
    target_asset_id: StableId
    path: tuple[PathStep, ...] = Field(min_length=1)
    risk: RiskComponents
    search: SearchMetadata
    baseline_detection: dict[AnalysisMethod, bool] = Field(default_factory=dict)
    caveats: tuple[str, ...] = ()


class IdentityRiskScore(StrictModel):
    node_id: StableId
    critical_reach: float = Field(ge=0, le=1)
    best_path: float = Field(ge=0, le=1)
    path_diversity: float = Field(ge=0, le=1)
    blast_radius: float = Field(ge=0, le=1)
    control_weakness: float = Field(ge=0, le=1)
    ztri: float = Field(ge=0, le=100)
