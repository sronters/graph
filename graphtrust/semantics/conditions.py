"""Tri-state evaluation for the normalized Boolean condition AST."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal

from graphtrust.schemas.conditions import (
    ConditionContext,
    ConditionExpression,
    ConditionOperand,
    ConditionState,
)

ConditionMode = Literal["conservative", "strict"]


def _compare(actual: Any, comparator: str, expected: Any) -> bool:
    if comparator == "EQ":
        return bool(actual == expected)
    if comparator == "NE":
        return bool(actual != expected)
    if comparator == "LT":
        return bool(actual < expected)
    if comparator == "LTE":
        return bool(actual <= expected)
    if comparator == "GT":
        return bool(actual > expected)
    if comparator == "GTE":
        return bool(actual >= expected)
    if comparator == "IN":
        return bool(actual in expected)
    if comparator == "CONTAINS":
        if isinstance(actual, Mapping) and isinstance(expected, Mapping):
            return all(actual.get(key) == value for key, value in expected.items())
        return bool(expected in actual)
    raise ValueError(f"Unsupported comparator: {comparator}")


def _time_window_state(context: ConditionContext, expected: Any) -> ConditionState:
    if not isinstance(expected, Mapping):
        return ConditionState.UNKNOWN
    start_value = expected.get("start")
    end_value = expected.get("end")
    if not isinstance(start_value, str) or not isinstance(end_value, str):
        return ConditionState.UNKNOWN
    try:
        start = datetime.fromisoformat(start_value)
        end = datetime.fromisoformat(end_value)
    except ValueError:
        return ConditionState.UNKNOWN
    return ConditionState.TRUE if start <= context.evaluated_at <= end else ConditionState.FALSE


def _operand_value(operand: ConditionOperand, context: ConditionContext) -> Any:
    values: dict[ConditionOperand, Any] = {
        ConditionOperand.ENVIRONMENT: context.environment,
        ConditionOperand.AUTHENTICATION_STRENGTH: context.authentication_strength,
        ConditionOperand.SOURCE_NETWORK_ZONE: context.source_network_zone,
        ConditionOperand.DEVICE_COMPLIANCE: context.device_compliant,
        ConditionOperand.RESOURCE_TAG: context.resource_tags,
        ConditionOperand.PRINCIPAL_TAG: context.principal_tags,
        ConditionOperand.TENANT_BOUNDARY: (
            None
            if context.principal_tenant is None or context.resource_tenant is None
            else context.principal_tenant == context.resource_tenant
        ),
        ConditionOperand.EXPLICIT_DENY: context.explicit_deny,
        ConditionOperand.SESSION_DURATION: context.session_duration_minutes,
        ConditionOperand.APPROVAL_REQUIRED: context.approval_granted,
    }
    return values.get(operand)


def evaluate_condition(
    expression: ConditionExpression, context: ConditionContext
) -> ConditionState:
    """Evaluate an AST using Kleene-style three-valued Boolean logic."""
    if expression.operator == "LEAF":
        if expression.operand is ConditionOperand.TIME_WINDOW:
            return _time_window_state(context, expression.expected)
        if expression.operand is None or expression.comparator is None:
            return ConditionState.UNKNOWN
        actual = _operand_value(expression.operand, context)
        if actual is None:
            return ConditionState.UNKNOWN
        try:
            result = _compare(actual, expression.comparator, expression.expected)
        except (TypeError, ValueError):
            return ConditionState.UNKNOWN
        return ConditionState.TRUE if result else ConditionState.FALSE

    states = tuple(evaluate_condition(child, context) for child in expression.children)
    if expression.operator == "NOT":
        if states[0] is ConditionState.UNKNOWN:
            return ConditionState.UNKNOWN
        return ConditionState.FALSE if states[0] is ConditionState.TRUE else ConditionState.TRUE
    if expression.operator == "AND":
        if ConditionState.FALSE in states:
            return ConditionState.FALSE
        if ConditionState.UNKNOWN in states:
            return ConditionState.UNKNOWN
        return ConditionState.TRUE
    if ConditionState.TRUE in states:
        return ConditionState.TRUE
    if ConditionState.UNKNOWN in states:
        return ConditionState.UNKNOWN
    return ConditionState.FALSE


def condition_is_traversable(state: ConditionState, mode: ConditionMode) -> bool:
    """Apply conservative or strict handling without changing recorded state."""
    return state is ConditionState.TRUE or (
        state is ConditionState.UNKNOWN and mode == "conservative"
    )
