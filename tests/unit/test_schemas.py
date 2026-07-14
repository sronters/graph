"""Schema invariants that protect canonical graph semantics."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from graphtrust.schemas.conditions import ConditionExpression, ConditionOperand
from graphtrust.schemas.edges import EdgeEffect, EdgeType, GraphEdge
from graphtrust.schemas.nodes import (
    Environment,
    GraphNode,
    IdentityStatus,
    NodeType,
    PrivilegeLabel,
    Provider,
)
from graphtrust.schemas.remediation import RemediationPlan, SolverName, SolverStatus


def make_node(**overrides: object) -> GraphNode:
    values: dict[str, object] = {
        "node_id": "human:1",
        "node_type": NodeType.HUMAN_IDENTITY,
        "display_name": "Synthetic Engineer 1",
        "provider": Provider.INTERNAL,
        "tenant_id": "tenant:1",
        "environment": Environment.CORPORATE,
        "department": "Engineering",
        "criticality": 0.1,
        "privilege_label": PrivilegeLabel.LOW,
        "identity_status": IdentityStatus.ACTIVE,
        "authentication_strength": 0.8,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "last_used_at": datetime(2026, 6, 1, tzinfo=UTC),
        "tags_json": '{"team":"payments","region":"EU"}',
        "generator_seed": 104729,
    }
    values.update(overrides)
    return GraphNode.model_validate(values)


def make_edge(**overrides: object) -> GraphEdge:
    values: dict[str, object] = {
        "edge_id": "edge:1",
        "source_id": "human:1",
        "target_id": "group:1",
        "edge_type": EdgeType.MEMBER_OF,
        "provider": Provider.INTERNAL,
        "effect": EdgeEffect.ALLOW,
        "relative_exploitability": 0.9,
        "business_removal_cost": 1.0,
        "source_artifact": "fixture",
    }
    values.update(overrides)
    return GraphEdge.model_validate(values)


def test_node_normalizes_json_and_hides_truth() -> None:
    node = make_node(ground_truth_labels_json='{"scenario":"S1"}')
    assert node.tags_json == '{"region":"EU","team":"payments"}'
    assert node.truth_hidden().ground_truth_labels_json is None


def test_node_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone-aware UTC"):
        make_node(created_at=datetime(2026, 1, 1))


def test_conditional_edge_requires_condition() -> None:
    with pytest.raises(ValidationError, match="require condition_id"):
        make_edge(effect=EdgeEffect.CONDITIONAL)


def test_derived_edge_requires_named_rule() -> None:
    with pytest.raises(ValidationError, match="derivation_rule"):
        make_edge(derived=True)


def test_protected_edge_is_not_removable() -> None:
    with pytest.raises(ValidationError, match="cannot be removable"):
        make_edge(protected=True, removable=True)


def test_condition_ast_enforces_shape() -> None:
    leaf = ConditionExpression(
        operator="LEAF",
        operand=ConditionOperand.APPROVAL_REQUIRED,
        comparator="EQ",
        expected=True,
    )
    expression = ConditionExpression(operator="NOT", children=(leaf,))
    assert expression.children == (leaf,)

    with pytest.raises(ValidationError, match="exactly one child"):
        ConditionExpression(operator="NOT", children=())


def test_verified_remediation_must_preserve_workflows() -> None:
    with pytest.raises(ValidationError, match="cannot break protected workflows"):
        RemediationPlan(
            plan_id="plan:1",
            solver=SolverName.MIN_CUT,
            status=SolverStatus.FEASIBLE,
            removed_edge_ids=("edge:1",),
            modeled_cost=1,
            blocked_path_ids=("path:1",),
            residual_exposure=0,
            protected_workflows_preserved=False,
            counterfactual_verified=True,
        )
