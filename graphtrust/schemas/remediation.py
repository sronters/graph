"""Remediation request, plan, and workflow schemas."""

from enum import StrEnum

from pydantic import Field, model_validator

from graphtrust.schemas.base import StrictModel
from graphtrust.schemas.nodes import StableId


class SolverName(StrEnum):
    DEGREE_GREEDY = "degree_greedy"
    RISK_GREEDY = "risk_greedy"
    MIN_CUT = "min_cut"
    CONSTRAINT_GENERATION = "constraint_generation"


class SolverStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    TIME_LIMIT = "TIME_LIMIT"
    ERROR = "ERROR"


class BusinessRequirement(StrictModel):
    requirement_id: StableId
    source_set: frozenset[StableId] = Field(min_length=1)
    target_set: frozenset[StableId] = Field(min_length=1)
    required_capability: str
    minimum_remaining_paths: int = Field(ge=1)
    maximum_path_length: int = Field(ge=1)
    priority: int = Field(ge=0)


class RemediationConstraints(StrictModel):
    maximum_changes: int | None = Field(default=None, ge=1)
    maximum_cost: float | None = Field(default=None, gt=0)
    maximum_changes_by_department: dict[str, int] = Field(default_factory=dict)
    maximum_changes_by_provider: dict[str, int] = Field(default_factory=dict)


class RemediationPlan(StrictModel):
    plan_id: StableId
    solver: SolverName
    status: SolverStatus
    removed_edge_ids: tuple[StableId, ...]
    modeled_cost: float = Field(ge=0)
    blocked_path_ids: tuple[StableId, ...]
    residual_exposure: float = Field(ge=0, le=1)
    affected_departments: tuple[str, ...] = ()
    protected_workflows_preserved: bool
    counterfactual_verified: bool
    optimality_bound: float | None = Field(default=None, ge=0)
    optimality_gap: float | None = Field(default=None, ge=0)
    iterations: int = Field(default=0, ge=0)
    added_constraints: int = Field(default=0, ge=0)
    runtime_seconds: float = Field(default=0, ge=0)
    caveats: tuple[str, ...] = (
        "Recommendation only; no live permission changes are executed.",
        "Optimality is relative to modeled costs and constraints.",
    )

    @model_validator(mode="after")
    def verified_plans_must_preserve_requirements(self) -> "RemediationPlan":
        if self.counterfactual_verified and not self.protected_workflows_preserved:
            raise ValueError("a verified plan cannot break protected workflows")
        return self
