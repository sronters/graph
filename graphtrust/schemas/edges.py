"""Canonical raw-edge model and enums."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, model_validator

from graphtrust.schemas.base import StrictModel
from graphtrust.schemas.nodes import Provider, StableId


class EdgeType(StrEnum):
    MEMBER_OF = "MEMBER_OF"
    NESTED_IN = "NESTED_IN"
    ASSIGNED_ROLE = "ASSIGNED_ROLE"
    ASSUMES_ROLE = "ASSUMES_ROLE"
    CAN_IMPERSONATE = "CAN_IMPERSONATE"
    TRUSTS_PRINCIPAL = "TRUSTS_PRINCIPAL"
    GRANTS_PERMISSION = "GRANTS_PERMISSION"
    POLICY_ATTACHED_TO = "POLICY_ATTACHED_TO"
    APPLIES_TO = "APPLIES_TO"
    INHERITS_FROM = "INHERITS_FROM"
    OWNS = "OWNS"
    MANAGES = "MANAGES"
    CAN_MODIFY = "CAN_MODIFY"
    CAN_CREATE_CREDENTIAL = "CAN_CREATE_CREDENTIAL"
    CAN_TRIGGER = "CAN_TRIGGER"
    RUNS_AS = "RUNS_AS"
    DEPLOYS_TO = "DEPLOYS_TO"
    READS = "READS"
    WRITES = "WRITES"
    ADMINISTERS = "ADMINISTERS"
    FEDERATES_TO = "FEDERATES_TO"
    APPROVED_ACCESS = "APPROVED_ACCESS"
    DENIES = "DENIES"


class EdgeEffect(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    CONDITIONAL = "CONDITIONAL"


class GraphEdge(StrictModel):
    """One evidence-preserving relationship in the raw multigraph."""

    edge_id: StableId
    source_id: StableId
    target_id: StableId
    edge_type: EdgeType
    provider: Provider
    effect: EdgeEffect
    scope: str = "*"
    condition_id: StableId | None = None
    direct: bool = True
    derived: bool = False
    derivation_rule: str | None = None
    confidence: float = Field(default=1, ge=0, le=1)
    relative_exploitability: float = Field(gt=0, le=1)
    business_removal_cost: float = Field(gt=0)
    removable: bool = True
    protected: bool = False
    active: bool = True
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    source_artifact: str
    ground_truth_scenario_id: str | None = None

    @model_validator(mode="after")
    def validate_semantics(self) -> "GraphEdge":
        for value in (self.valid_from, self.valid_until):
            if value is not None and (
                value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)
            ):
                raise ValueError("edge validity timestamps must be timezone-aware UTC")
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise ValueError("valid_from must not be after valid_until")
        if self.derived and not self.derivation_rule:
            raise ValueError("derived edges require a named derivation_rule")
        if self.protected and self.removable:
            raise ValueError("protected edges cannot be removable")
        if self.effect is EdgeEffect.CONDITIONAL and self.condition_id is None:
            raise ValueError("conditional edges require condition_id")
        return self

    def truth_hidden(self) -> "GraphEdge":
        """Return an inference-safe copy without planted scenario labels."""
        return self.model_copy(update={"ground_truth_scenario_id": None})
