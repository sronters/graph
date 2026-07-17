"""Table-driven semantic fixtures and derived-rule validation."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from graphtrust.schemas.conditions import (
    Condition,
    ConditionContext,
    ConditionExpression,
    ConditionOperand,
)
from graphtrust.schemas.edges import EdgeEffect, EdgeType, GraphEdge
from graphtrust.schemas.nodes import (
    Environment,
    GraphNode,
    IdentityStatus,
    NodeType,
    PrivilegeLabel,
    Provider,
)
from graphtrust.semantics.compiler import SemanticCompiler

NOW = datetime(2026, 7, 14, 12, tzinfo=UTC)


def node(
    node_id: str,
    node_type: NodeType,
    *,
    status: IdentityStatus = IdentityStatus.NOT_APPLICABLE,
    tenant: str = "tenant:1",
    environment: Environment = Environment.PROD,
    authentication_strength: float = 0.8,
) -> GraphNode:
    return GraphNode(
        node_id=node_id,
        node_type=node_type,
        display_name=f"Synthetic {node_id}",
        provider=Provider.GENERIC,
        tenant_id=tenant,
        environment=environment,
        department="Engineering",
        criticality=0.9 if node_type in {NodeType.DATABASE, NodeType.CRITICAL_ASSET} else 0.1,
        privilege_label=PrivilegeLabel.LOW,
        identity_status=status,
        authentication_strength=authentication_strength,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tags_json="{}",
        generator_seed=104729,
    )


def raw_edge(
    edge_id: str,
    source: str,
    target: str,
    edge_type: EdgeType,
    *,
    effect: EdgeEffect = EdgeEffect.ALLOW,
    condition_id: str | None = None,
    active: bool = True,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
    protected: bool = False,
) -> GraphEdge:
    return GraphEdge(
        edge_id=edge_id,
        source_id=source,
        target_id=target,
        edge_type=edge_type,
        provider=Provider.GENERIC,
        effect=effect,
        condition_id=condition_id,
        relative_exploitability=0.8,
        business_removal_cost=1,
        removable=not protected,
        protected=protected,
        active=active,
        valid_from=valid_from,
        valid_until=valid_until,
        source_artifact="semantic-fixture",
    )


@dataclass(frozen=True)
class SemanticFixture:
    name: str
    edge_type: EdgeType = EdgeType.READS
    source_type: NodeType = NodeType.HUMAN_IDENTITY
    source_status: IdentityStatus = IdentityStatus.ACTIVE
    effect: EdgeEffect = EdgeEffect.ALLOW
    active: bool = True
    validity: str = "current"
    protected: bool = False
    condition_operand: ConditionOperand | None = None
    condition_expected: object = None
    context_value: object = None
    mode: str = "conservative"
    include_disabled: bool = False
    target_tenant: str = "tenant:1"
    expected_effective: int = 1
    expected_rejected: int = 0


SEMANTIC_FIXTURES = (
    SemanticFixture("direct_read", EdgeType.READS),
    SemanticFixture("direct_write", EdgeType.WRITES),
    SemanticFixture("direct_admin", EdgeType.ADMINISTERS),
    SemanticFixture("direct_modify", EdgeType.CAN_MODIFY),
    SemanticFixture("role_assumption", EdgeType.ASSUMES_ROLE),
    SemanticFixture("human_impersonation", EdgeType.CAN_IMPERSONATE),
    SemanticFixture("pipeline_trigger", EdgeType.CAN_TRIGGER),
    SemanticFixture("workload_runs_as", EdgeType.RUNS_AS),
    SemanticFixture("deployment_control", EdgeType.DEPLOYS_TO),
    SemanticFixture("cross_tenant_federation", EdgeType.FEDERATES_TO, target_tenant="tenant:2"),
    SemanticFixture("approval_edge_unconditional", EdgeType.APPROVED_ACCESS),
    SemanticFixture("management_control", EdgeType.MANAGES),
    SemanticFixture("ownership_control", EdgeType.OWNS),
    SemanticFixture("credential_creation", EdgeType.CAN_CREATE_CREDENTIAL),
    SemanticFixture("protected_relationship", EdgeType.READS, protected=True),
    SemanticFixture(
        "inactive_relationship", active=False, expected_effective=0, expected_rejected=1
    ),
    SemanticFixture(
        "expired_assignment", validity="expired", expected_effective=0, expected_rejected=1
    ),
    SemanticFixture(
        "future_assignment", validity="future", expected_effective=0, expected_rejected=1
    ),
    SemanticFixture(
        "disabled_identity",
        source_status=IdentityStatus.DISABLED,
        expected_effective=0,
        expected_rejected=1,
    ),
    SemanticFixture(
        "disabled_identity_sensitivity",
        source_status=IdentityStatus.DISABLED,
        include_disabled=True,
    ),
    SemanticFixture(
        "environment_true",
        effect=EdgeEffect.CONDITIONAL,
        condition_operand=ConditionOperand.ENVIRONMENT,
        condition_expected="PROD",
        context_value="PROD",
    ),
    SemanticFixture(
        "environment_false",
        effect=EdgeEffect.CONDITIONAL,
        condition_operand=ConditionOperand.ENVIRONMENT,
        condition_expected="PROD",
        context_value="DEV",
        expected_effective=0,
        expected_rejected=1,
    ),
    SemanticFixture(
        "unknown_conservative",
        effect=EdgeEffect.CONDITIONAL,
        condition_operand=ConditionOperand.DEVICE_COMPLIANCE,
        condition_expected=True,
    ),
    SemanticFixture(
        "unknown_strict",
        effect=EdgeEffect.CONDITIONAL,
        condition_operand=ConditionOperand.DEVICE_COMPLIANCE,
        condition_expected=True,
        mode="strict",
        expected_effective=0,
        expected_rejected=1,
    ),
    SemanticFixture(
        "authentication_true",
        effect=EdgeEffect.CONDITIONAL,
        condition_operand=ConditionOperand.AUTHENTICATION_STRENGTH,
        condition_expected=0.7,
        context_value=0.9,
    ),
    SemanticFixture(
        "authentication_false",
        effect=EdgeEffect.CONDITIONAL,
        condition_operand=ConditionOperand.AUTHENTICATION_STRENGTH,
        condition_expected=0.9,
        context_value=0.5,
        expected_effective=0,
        expected_rejected=1,
    ),
    SemanticFixture(
        "approval_true",
        effect=EdgeEffect.CONDITIONAL,
        condition_operand=ConditionOperand.APPROVAL_REQUIRED,
        condition_expected=True,
        context_value=True,
    ),
    SemanticFixture(
        "approval_unknown_conservative",
        effect=EdgeEffect.CONDITIONAL,
        condition_operand=ConditionOperand.APPROVAL_REQUIRED,
        condition_expected=True,
    ),
    SemanticFixture(
        "tenant_boundary_same",
        effect=EdgeEffect.CONDITIONAL,
        condition_operand=ConditionOperand.TENANT_BOUNDARY,
        condition_expected=True,
        context_value=True,
    ),
    SemanticFixture(
        "tenant_boundary_cross",
        effect=EdgeEffect.CONDITIONAL,
        condition_operand=ConditionOperand.TENANT_BOUNDARY,
        condition_expected=True,
        context_value=False,
        target_tenant="tenant:2",
        expected_effective=0,
        expected_rejected=1,
    ),
    SemanticFixture(
        "service_account_impersonation",
        edge_type=EdgeType.CAN_IMPERSONATE,
        source_type=NodeType.SERVICE_ACCOUNT,
        source_status=IdentityStatus.ACTIVE,
    ),
)


def condition_context(fixture: SemanticFixture) -> ConditionContext:
    values: dict[str, object] = {"evaluated_at": NOW}
    key_by_operand = {
        ConditionOperand.ENVIRONMENT: "environment",
        ConditionOperand.AUTHENTICATION_STRENGTH: "authentication_strength",
        ConditionOperand.DEVICE_COMPLIANCE: "device_compliant",
        ConditionOperand.APPROVAL_REQUIRED: "approval_granted",
    }
    if fixture.condition_operand is ConditionOperand.TENANT_BOUNDARY:
        values["principal_tenant"] = "tenant:1"
        values["resource_tenant"] = fixture.target_tenant
    elif fixture.condition_operand in key_by_operand and fixture.context_value is not None:
        values[key_by_operand[fixture.condition_operand]] = fixture.context_value
    return ConditionContext.model_validate(values)


@pytest.mark.parametrize("fixture", SEMANTIC_FIXTURES, ids=lambda item: item.name)
def test_semantic_fixture(fixture: SemanticFixture) -> None:
    source = node(
        "source",
        fixture.source_type,
        status=fixture.source_status,
    )
    target_type = (
        NodeType.ROLE
        if fixture.edge_type
        in {
            EdgeType.ASSUMES_ROLE,
            EdgeType.CAN_IMPERSONATE,
            EdgeType.FEDERATES_TO,
            EdgeType.RUNS_AS,
        }
        else NodeType.DATABASE
    )
    target = node("target", target_type, tenant=fixture.target_tenant)
    valid_from = NOW + timedelta(days=1) if fixture.validity == "future" else None
    valid_until = NOW - timedelta(days=1) if fixture.validity == "expired" else None
    condition_id = "condition:1" if fixture.condition_operand else None
    edge = raw_edge(
        "edge:1",
        source.node_id,
        target.node_id,
        fixture.edge_type,
        effect=fixture.effect,
        condition_id=condition_id,
        active=fixture.active,
        valid_from=valid_from,
        valid_until=valid_until,
        protected=fixture.protected,
    )
    conditions = ()
    contexts: dict[str, ConditionContext] = {}
    if fixture.condition_operand:
        comparator = (
            "GTE" if fixture.condition_operand is ConditionOperand.AUTHENTICATION_STRENGTH else "EQ"
        )
        conditions = (
            Condition(
                condition_id="condition:1",
                expression=ConditionExpression(
                    operator="LEAF",
                    operand=fixture.condition_operand,
                    comparator=comparator,
                    expected=fixture.condition_expected,
                ),
            ),
        )
        contexts[source.node_id] = condition_context(fixture)
    result = SemanticCompiler(
        condition_mode="strict" if fixture.mode == "strict" else "conservative",
        evaluated_at=NOW,
        include_disabled=fixture.include_disabled,
    ).compile((source, target), (edge,), conditions, contexts)

    assert len(result.effective_edges) == fixture.expected_effective
    assert len(result.rejected_edges) == fixture.expected_rejected
    if fixture.protected:
        assert result.effective_edges[0].business_removal_candidates == ()


def test_explicit_deny_blocks_matching_allow() -> None:
    source = node("human", NodeType.HUMAN_IDENTITY, status=IdentityStatus.ACTIVE)
    target = node("database", NodeType.DATABASE)
    allow = raw_edge("allow", "human", "database", EdgeType.READS)
    deny = raw_edge("deny", "human", "database", EdgeType.DENIES, effect=EdgeEffect.DENY)
    result = SemanticCompiler(evaluated_at=NOW).compile((source, target), (allow, deny))
    assert result.effective_edges == ()
    assert result.rejected_edges[0].semantic_rule_id == "explicit_deny_precedence"


def test_nested_groups_derive_role_with_full_provenance_and_report_cycle() -> None:
    human = node("human", NodeType.HUMAN_IDENTITY, status=IdentityStatus.ACTIVE)
    group_a = node("group:a", NodeType.GROUP)
    group_b = node("group:b", NodeType.GROUP)
    role = node("role", NodeType.ROLE)
    edges = (
        raw_edge("member", "human", "group:a", EdgeType.MEMBER_OF),
        raw_edge("nested:ab", "group:a", "group:b", EdgeType.NESTED_IN),
        raw_edge("nested:ba", "group:b", "group:a", EdgeType.NESTED_IN),
        raw_edge("assignment", "group:b", "role", EdgeType.ASSIGNED_ROLE),
    )
    result = SemanticCompiler(evaluated_at=NOW).compile((human, group_a, group_b, role), edges)
    derived = [
        edge
        for edge in result.effective_edges
        if edge.semantic_rule_id == "nested_group_role_assignment"
    ]
    assert len(derived) == 1
    assert derived[0].raw_evidence_edge_ids == ("member", "nested:ab", "assignment")
    assert result.group_cycles
    assert result.warnings


def test_deeply_nested_groups_do_not_exceed_recursion_limit() -> None:
    """Regression test for the RecursionError observed on the large-scale
    profile, where a NESTED_IN chain ~990 groups deep overflowed Python's
    default recursion limit inside the (formerly recursive) cycle detector.
    This chain is deliberately longer than that limit and is acyclic, so a
    correct iterative implementation must both avoid the RecursionError and
    report zero cycles.
    """
    depth = 1500
    human = node("human", NodeType.HUMAN_IDENTITY, status=IdentityStatus.ACTIVE)
    groups = [node(f"group:{index}", NodeType.GROUP) for index in range(depth + 1)]
    role = node("role", NodeType.ROLE)
    edges = [raw_edge("member", "human", "group:0", EdgeType.MEMBER_OF)]
    edges.extend(
        raw_edge(f"nested:{index}", f"group:{index}", f"group:{index + 1}", EdgeType.NESTED_IN)
        for index in range(depth)
    )
    edges.append(raw_edge("assignment", f"group:{depth}", "role", EdgeType.ASSIGNED_ROLE))

    result = SemanticCompiler(evaluated_at=NOW).compile((human, *groups, role), tuple(edges))

    assert result.group_cycles == ()
    derived = [
        edge
        for edge in result.effective_edges
        if edge.semantic_rule_id == "nested_group_role_assignment"
    ]
    assert len(derived) == 1
    assert len(derived[0].raw_evidence_edge_ids) == depth + 2


def test_attached_policy_and_parent_scope_rules_are_named() -> None:
    human = node("human", NodeType.HUMAN_IDENTITY, status=IdentityStatus.ACTIVE)
    role = node("role", NodeType.ROLE)
    policy = node("policy", NodeType.POLICY)
    parent = node("folder", NodeType.CLOUD_FOLDER)
    child = node("database", NodeType.DATABASE)
    edges = (
        raw_edge("attach", "human", "policy", EdgeType.POLICY_ATTACHED_TO),
        raw_edge("grant", "policy", "folder", EdgeType.GRANTS_PERMISSION),
        raw_edge("role-read", "role", "folder", EdgeType.READS),
        raw_edge("inherit", "database", "folder", EdgeType.INHERITS_FROM),
    )
    result = SemanticCompiler(evaluated_at=NOW).compile((human, role, policy, parent, child), edges)
    rules = {edge.semantic_rule_id for edge in result.effective_edges}
    assert "attached_policy_grant" in rules
    assert "inherited_parent_scope" in rules
    assert all(edge.raw_evidence_edge_ids for edge in result.effective_edges)
