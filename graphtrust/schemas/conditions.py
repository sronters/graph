"""Normalized tri-state Boolean condition AST."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from graphtrust.schemas.base import StrictModel
from graphtrust.schemas.nodes import StableId


class ConditionState(StrEnum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


class ConditionOperand(StrEnum):
    TIME_WINDOW = "TIME_WINDOW"
    ENVIRONMENT = "ENVIRONMENT"
    AUTHENTICATION_STRENGTH = "AUTHENTICATION_STRENGTH"
    SOURCE_NETWORK_ZONE = "SOURCE_NETWORK_ZONE"
    DEVICE_COMPLIANCE = "DEVICE_COMPLIANCE"
    RESOURCE_TAG = "RESOURCE_TAG"
    PRINCIPAL_TAG = "PRINCIPAL_TAG"
    TENANT_BOUNDARY = "TENANT_BOUNDARY"
    EXPLICIT_DENY = "EXPLICIT_DENY"
    SESSION_DURATION = "SESSION_DURATION"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


class ConditionExpression(StrictModel):
    """Recursive AST node; leaf nodes carry an operand and comparison value."""

    operator: Literal["AND", "OR", "NOT", "LEAF"]
    operand: ConditionOperand | None = None
    comparator: Literal["EQ", "NE", "LT", "LTE", "GT", "GTE", "IN", "CONTAINS"] | None = None
    expected: Any | None = None
    children: tuple["ConditionExpression", ...] = ()

    @model_validator(mode="after")
    def validate_shape(self) -> "ConditionExpression":
        if self.operator == "LEAF":
            if self.operand is None or self.comparator is None or self.children:
                raise ValueError("leaf conditions require operand/comparator and no children")
        elif self.operator == "NOT":
            if len(self.children) != 1 or self.operand is not None:
                raise ValueError("NOT requires exactly one child")
        elif len(self.children) < 2 or self.operand is not None:
            raise ValueError("AND/OR require at least two children")
        return self


class Condition(StrictModel):
    """Stored normalized condition document."""

    condition_id: StableId
    expression: ConditionExpression
    source_text: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    @model_validator(mode="after")
    def validate_timestamps(self) -> "Condition":
        for value in (self.valid_from, self.valid_until):
            if value is not None and (
                value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)
            ):
                raise ValueError("condition timestamps must be timezone-aware UTC")
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise ValueError("valid_from must not be after valid_until")
        return self


class ConditionContext(StrictModel):
    """Known facts supplied when evaluating a condition."""

    evaluated_at: datetime
    environment: str | None = None
    authentication_strength: float | None = Field(default=None, ge=0, le=1)
    source_network_zone: str | None = None
    device_compliant: bool | None = None
    resource_tags: dict[str, Any] = Field(default_factory=dict)
    principal_tags: dict[str, Any] = Field(default_factory=dict)
    principal_tenant: str | None = None
    resource_tenant: str | None = None
    explicit_deny: bool | None = None
    session_duration_minutes: int | None = Field(default=None, ge=0)
    approval_granted: bool | None = None
