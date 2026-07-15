"""Tri-state condition semantics."""

from datetime import UTC, datetime

import pytest

from graphtrust.schemas.conditions import (
    ConditionContext,
    ConditionExpression,
    ConditionOperand,
    ConditionState,
)
from graphtrust.semantics import aws_like, azure_like, gcp_like, generic
from graphtrust.semantics.conditions import _compare, condition_is_traversable, evaluate_condition

NOW = datetime(2026, 7, 14, 12, tzinfo=UTC)


def leaf(
    operand: ConditionOperand,
    comparator: str,
    expected: object,
) -> ConditionExpression:
    return ConditionExpression.model_validate(
        {
            "operator": "LEAF",
            "operand": operand,
            "comparator": comparator,
            "expected": expected,
        }
    )


@pytest.mark.parametrize(
    ("expression", "context", "expected"),
    [
        (
            leaf(ConditionOperand.ENVIRONMENT, "EQ", "PROD"),
            ConditionContext(evaluated_at=NOW, environment="PROD"),
            ConditionState.TRUE,
        ),
        (
            leaf(ConditionOperand.AUTHENTICATION_STRENGTH, "GTE", 0.8),
            ConditionContext(evaluated_at=NOW, authentication_strength=0.5),
            ConditionState.FALSE,
        ),
        (
            leaf(ConditionOperand.DEVICE_COMPLIANCE, "EQ", True),
            ConditionContext(evaluated_at=NOW),
            ConditionState.UNKNOWN,
        ),
        (
            leaf(ConditionOperand.RESOURCE_TAG, "CONTAINS", {"data": "restricted"}),
            ConditionContext(evaluated_at=NOW, resource_tags={"data": "restricted"}),
            ConditionState.TRUE,
        ),
        (
            leaf(
                ConditionOperand.TIME_WINDOW,
                "IN",
                {"start": "2026-07-14T00:00:00+00:00", "end": "2026-07-15T00:00:00+00:00"},
            ),
            ConditionContext(evaluated_at=NOW),
            ConditionState.TRUE,
        ),
    ],
)
def test_leaf_conditions(
    expression: ConditionExpression,
    context: ConditionContext,
    expected: ConditionState,
) -> None:
    assert evaluate_condition(expression, context) is expected


def test_boolean_ast_uses_three_valued_logic() -> None:
    true = leaf(ConditionOperand.ENVIRONMENT, "EQ", "PROD")
    unknown = leaf(ConditionOperand.DEVICE_COMPLIANCE, "EQ", True)
    false = leaf(ConditionOperand.APPROVAL_REQUIRED, "EQ", True)
    context = ConditionContext(evaluated_at=NOW, environment="PROD", approval_granted=False)

    assert (
        evaluate_condition(ConditionExpression(operator="AND", children=(true, unknown)), context)
        is ConditionState.UNKNOWN
    )
    assert (
        evaluate_condition(ConditionExpression(operator="AND", children=(unknown, false)), context)
        is ConditionState.FALSE
    )
    assert (
        evaluate_condition(ConditionExpression(operator="OR", children=(unknown, true)), context)
        is ConditionState.TRUE
    )
    assert (
        evaluate_condition(ConditionExpression(operator="NOT", children=(unknown,)), context)
        is ConditionState.UNKNOWN
    )


def test_unknown_mode_boundary_is_explicit() -> None:
    assert condition_is_traversable(ConditionState.UNKNOWN, "conservative")
    assert not condition_is_traversable(ConditionState.UNKNOWN, "strict")
    assert condition_is_traversable(ConditionState.TRUE, "strict")
    assert not condition_is_traversable(ConditionState.FALSE, "conservative")


@pytest.mark.parametrize(
    ("actual", "comparator", "expected", "result"),
    [
        ("prod", "NE", "dev", True),
        (1, "LT", 2, True),
        (2, "LTE", 2, True),
        (3, "GT", 2, True),
        (3, "GTE", 3, True),
        ("prod", "IN", ["dev", "prod"], True),
        (["read", "write"], "CONTAINS", "write", True),
    ],
)
def test_comparator_contract(
    actual: object,
    comparator: str,
    expected: object,
    result: bool,
) -> None:
    assert _compare(actual, comparator, expected) is result


def test_invalid_comparator_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported comparator"):
        _compare(1, "INVALID", 1)


@pytest.mark.parametrize(
    "expected",
    [None, {}, {"start": 1, "end": 2}, {"start": "invalid", "end": "invalid"}],
)
def test_invalid_time_windows_are_unknown(expected: object) -> None:
    expression = leaf(ConditionOperand.TIME_WINDOW, "IN", expected)
    assert (
        evaluate_condition(expression, ConditionContext(evaluated_at=NOW)) is ConditionState.UNKNOWN
    )


def test_all_supported_context_operands_are_evaluated() -> None:
    context = ConditionContext(
        evaluated_at=NOW,
        source_network_zone="corporate",
        principal_tags={"team": "security"},
        principal_tenant="tenant:1",
        resource_tenant="tenant:2",
        explicit_deny=False,
        session_duration_minutes=30,
        approval_granted=True,
    )
    expressions = (
        leaf(ConditionOperand.SOURCE_NETWORK_ZONE, "EQ", "corporate"),
        leaf(ConditionOperand.PRINCIPAL_TAG, "CONTAINS", {"team": "security"}),
        leaf(ConditionOperand.TENANT_BOUNDARY, "EQ", False),
        leaf(ConditionOperand.EXPLICIT_DENY, "EQ", False),
        leaf(ConditionOperand.SESSION_DURATION, "LTE", 60),
        leaf(ConditionOperand.APPROVAL_REQUIRED, "EQ", True),
    )
    assert all(
        evaluate_condition(expression, context) is ConditionState.TRUE for expression in expressions
    )


def test_remaining_boolean_outcomes() -> None:
    true = leaf(ConditionOperand.ENVIRONMENT, "EQ", "PROD")
    false = leaf(ConditionOperand.ENVIRONMENT, "EQ", "DEV")
    context = ConditionContext(evaluated_at=NOW, environment="PROD")
    assert (
        evaluate_condition(ConditionExpression(operator="AND", children=(true, true)), context)
        is ConditionState.TRUE
    )
    assert (
        evaluate_condition(ConditionExpression(operator="OR", children=(false, false)), context)
        is ConditionState.FALSE
    )
    assert (
        evaluate_condition(ConditionExpression(operator="NOT", children=(true,)), context)
        is ConditionState.FALSE
    )
    assert (
        evaluate_condition(ConditionExpression(operator="NOT", children=(false,)), context)
        is ConditionState.TRUE
    )


def test_provider_scope_normalization_is_deterministic() -> None:
    assert generic.normalize_scope(" resource/path/ ") == "resource/path"
    assert generic.normalize_scope("/") == "/"
    assert generic.normalize_scope("") == "*"
    assert aws_like.normalize_scope("ARN:AWS:S3:::Bucket/") == "arn:AWS:S3:::Bucket"
    assert azure_like.normalize_scope("subscriptions/abc/") == "/subscriptions/abc"
    assert azure_like.normalize_scope("*") == "*"
    assert gcp_like.normalize_scope("Projects/ABC/") == "projects/abc"
