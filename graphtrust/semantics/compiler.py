"""Compile raw IAM relationships into evidence-preserving capability transitions."""

import hashlib
import json
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from graphtrust.schemas.conditions import Condition, ConditionContext, ConditionState
from graphtrust.schemas.edges import EdgeEffect, EdgeType, GraphEdge
from graphtrust.schemas.nodes import GraphNode, IdentityStatus, NodeType
from graphtrust.semantics.conditions import (
    ConditionMode,
    condition_is_traversable,
    evaluate_condition,
)
from graphtrust.semantics.effective_access import EffectiveCapabilityEdge, RejectedSemanticEdge

IDENTITY_TYPES = frozenset(
    {
        NodeType.HUMAN_IDENTITY,
        NodeType.SERVICE_ACCOUNT,
        NodeType.WORKLOAD_IDENTITY,
        NodeType.EXTERNAL_IDENTITY,
    }
)
IDENTITY_TRANSITIONS = frozenset(
    {
        EdgeType.ASSUMES_ROLE,
        EdgeType.CAN_IMPERSONATE,
        EdgeType.FEDERATES_TO,
        EdgeType.RUNS_AS,
    }
)
STRUCTURAL_EDGE_TYPES = frozenset(
    {
        EdgeType.MEMBER_OF,
        EdgeType.NESTED_IN,
        EdgeType.POLICY_ATTACHED_TO,
        EdgeType.INHERITS_FROM,
        EdgeType.DENIES,
        EdgeType.APPLIES_TO,
    }
)


@dataclass(frozen=True, slots=True)
class CompilationResult:
    """Compiler output and explicit exclusions."""

    effective_edges: tuple[EffectiveCapabilityEdge, ...]
    rejected_edges: tuple[RejectedSemanticEdge, ...]
    group_cycles: tuple[tuple[str, ...], ...]
    warnings: tuple[str, ...]


def _stable_effective_id(rule: str, actor: str, target: str, evidence: Sequence[str]) -> str:
    material = "\0".join((rule, actor, target, *sorted(evidence)))
    return "effective:" + hashlib.sha256(material.encode()).hexdigest()[:24]


def _removal_candidates(edges: Iterable[GraphEdge]) -> tuple[str, ...]:
    return tuple(sorted(edge.edge_id for edge in edges if edge.removable and not edge.protected))


def _detect_group_cycles(
    adjacency: Mapping[str, Sequence[tuple[str, GraphEdge]]],
) -> tuple[tuple[str, ...], ...]:
    """Iterative 3-color DFS cycle detection.

    Behaviorally identical to a recursive `visit(node)` walk (same
    active/complete/visiting state machine and the same min-rotation cycle
    canonicalization), but implemented with an explicit stack instead of the
    Python call stack. Deeply nested `NESTED_IN` chains (observed at ~990
    levels on the large-scale profile) exceed Python's default recursion
    limit under the recursive form; this form has no such ceiling.
    """
    cycles: set[tuple[str, ...]] = set()
    visiting: list[str] = []
    active: set[str] = set()
    complete: set[str] = set()

    def push(node: str, stack: list[tuple[str, Iterable[str]]]) -> None:
        """Push node's frame onto `stack` if unvisited, else record a cycle.

        `stack` is passed explicitly (rather than closed over) so this
        closure has no loop-scoped free variables: it is redefined once,
        outside any loop, and every call site supplies the current stack.
        """
        if node in complete:
            return
        if node in active:
            start = visiting.index(node)
            cycle = [*visiting[start:], node]
            rotations = [
                tuple(cycle[index:-1] + cycle[: index + 1]) for index in range(len(cycle) - 1)
            ]
            cycles.add(min(rotations))
            return
        active.add(node)
        visiting.append(node)
        children = iter([target for target, _ in adjacency.get(node, ())])
        stack.append((node, children))

    for start_group in sorted(adjacency):
        if start_group in complete:
            continue
        # Each stack frame is (node, iterator over its children). This
        # mirrors the recursive version's call frame: work done on first
        # visiting `node` happens when the frame is pushed; work done after
        # all children are exhausted happens when the frame is popped.
        stack: list[tuple[str, Iterable[str]]] = []
        push(start_group, stack)
        while stack:
            node, children = stack[-1]
            next_child = next(children, None)
            if next_child is None:
                # All children exhausted: finalize this node, matching the
                # recursive version's post-recursion cleanup.
                stack.pop()
                visiting.pop()
                active.remove(node)
                complete.add(node)
                continue
            push(next_child, stack)

    return tuple(sorted(cycles))


class SemanticCompiler:
    """Deterministic normalized authorization compiler."""

    def __init__(
        self,
        *,
        condition_mode: ConditionMode = "conservative",
        evaluated_at: datetime | None = None,
        include_disabled: bool = False,
    ) -> None:
        self.condition_mode = condition_mode
        self.evaluated_at = evaluated_at or datetime.now(tz=UTC)
        self.include_disabled = include_disabled

    def _context(self, source: GraphNode, target: GraphNode) -> ConditionContext:
        return ConditionContext(
            evaluated_at=self.evaluated_at,
            environment=source.environment.value,
            authentication_strength=source.authentication_strength,
            principal_tags=json.loads(source.tags_json),
            resource_tags=json.loads(target.tags_json),
            principal_tenant=source.tenant_id,
            resource_tenant=target.tenant_id,
            explicit_deny=False,
        )

    def _edge_state(
        self,
        edge: GraphEdge,
        source: GraphNode,
        target: GraphNode,
        conditions: Mapping[str, Condition],
        contexts: Mapping[str, ConditionContext],
    ) -> ConditionState:
        if edge.effect is not EdgeEffect.CONDITIONAL:
            return ConditionState.TRUE
        condition = conditions.get(edge.condition_id or "")
        if condition is None:
            return ConditionState.UNKNOWN
        return evaluate_condition(
            condition.expression, contexts.get(source.node_id, self._context(source, target))
        )

    def _raw_eligible_reason(
        self,
        edge: GraphEdge,
        source: GraphNode,
        state: ConditionState,
    ) -> str | None:
        if not edge.active:
            return "inactive relationship"
        if edge.valid_from and self.evaluated_at < edge.valid_from:
            return "relationship not yet valid"
        if edge.valid_until and self.evaluated_at > edge.valid_until:
            return "expired relationship"
        if (
            source.node_type in IDENTITY_TYPES
            and source.identity_status is IdentityStatus.DISABLED
            and not self.include_disabled
        ):
            return "disabled starting identity"
        if state is ConditionState.FALSE:
            return "condition evaluated false"
        if not condition_is_traversable(state, self.condition_mode):
            return "unknown condition excluded in strict mode"
        return None

    def _make_effective(
        self,
        *,
        actor: GraphNode,
        target: GraphNode,
        raw_edges: Sequence[GraphEdge],
        rule: str,
        capability: str,
        transition_type: str,
        condition_state: ConditionState,
    ) -> EffectiveCapabilityEdge:
        actor_after = (
            target.node_id if raw_edges[-1].edge_type in IDENTITY_TRANSITIONS else actor.node_id
        )
        risk = 1.0
        for edge in raw_edges:
            risk *= edge.relative_exploitability
        evidence = tuple(edge.edge_id for edge in raw_edges)
        return EffectiveCapabilityEdge(
            edge_id=_stable_effective_id(rule, actor.node_id, target.node_id, evidence),
            actor_before=actor.node_id,
            actor_after=actor_after,
            resource_or_identity_target=target.node_id,
            capability=capability,
            transition_type=transition_type,
            condition_state=condition_state,
            relative_exploitability=max(min(risk, 1.0), 1e-12),
            control_strength=max(0.0, min(1.0, actor.authentication_strength)),
            business_removal_candidates=_removal_candidates(raw_edges),
            raw_evidence_edge_ids=evidence,
            semantic_rule_id=rule,
            source_provider=raw_edges[-1].provider.value,
        )

    def compile(
        self,
        nodes: Sequence[GraphNode],
        edges: Sequence[GraphEdge],
        conditions: Sequence[Condition] = (),
        contexts: Mapping[str, ConditionContext] | None = None,
    ) -> CompilationResult:
        """Compile raw relationships using documented deterministic rules."""
        node_by_id = {node.node_id: node for node in nodes}
        condition_by_id = {condition.condition_id: condition for condition in conditions}
        provided_contexts = contexts or {}
        rejected: list[RejectedSemanticEdge] = []
        warnings: list[str] = []
        eligible: dict[str, tuple[GraphEdge, ConditionState]] = {}

        for edge in sorted(edges, key=lambda item: item.edge_id):
            source = node_by_id.get(edge.source_id)
            target = node_by_id.get(edge.target_id)
            if source is None or target is None:
                rejected.append(
                    RejectedSemanticEdge(
                        raw_evidence_edge_ids=(edge.edge_id,),
                        semantic_rule_id="referential_validation",
                        reason="unknown source or target node",
                    )
                )
                continue
            state = self._edge_state(edge, source, target, condition_by_id, provided_contexts)
            reason = self._raw_eligible_reason(edge, source, state)
            if reason:
                rejected.append(
                    RejectedSemanticEdge(
                        raw_evidence_edge_ids=(edge.edge_id,),
                        semantic_rule_id="raw_edge_eligibility",
                        reason=reason,
                    )
                )
                continue
            eligible[edge.edge_id] = (edge, state)

        eligible_edges = [value[0] for value in eligible.values()]
        deny_keys = {
            (edge.source_id, edge.target_id, edge.scope)
            for edge in eligible_edges
            if edge.edge_type is EdgeType.DENIES or edge.effect is EdgeEffect.DENY
        }

        def denied(actor_id: str, target_id: str, scope: str) -> bool:
            return (actor_id, target_id, scope) in deny_keys or (
                actor_id,
                target_id,
                "*",
            ) in deny_keys

        effective: dict[str, EffectiveCapabilityEdge] = {}
        for edge in eligible_edges:
            if edge.edge_type in STRUCTURAL_EDGE_TYPES or edge.effect is EdgeEffect.DENY:
                continue
            source = node_by_id[edge.source_id]
            target = node_by_id[edge.target_id]
            if edge.edge_type is EdgeType.ASSIGNED_ROLE and source.node_type is NodeType.GROUP:
                continue
            if denied(source.node_id, target.node_id, edge.scope):
                rejected.append(
                    RejectedSemanticEdge(
                        raw_evidence_edge_ids=(edge.edge_id,),
                        semantic_rule_id="explicit_deny_precedence",
                        reason="matching explicit deny",
                    )
                )
                continue
            state = eligible[edge.edge_id][1]
            rule = (
                "direct_role_assignment"
                if edge.edge_type is EdgeType.ASSIGNED_ROLE
                else "direct_capability_transition"
            )
            compiled = self._make_effective(
                actor=source,
                target=target,
                raw_edges=(edge,),
                rule=rule,
                capability=edge.edge_type.value,
                transition_type=edge.edge_type.value,
                condition_state=state,
            )
            effective[compiled.edge_id] = compiled

        group_adjacency: dict[str, list[tuple[str, GraphEdge]]] = defaultdict(list)
        memberships: list[GraphEdge] = []
        group_role_edges: dict[str, list[GraphEdge]] = defaultdict(list)
        for edge in eligible_edges:
            if edge.edge_type is EdgeType.NESTED_IN:
                group_adjacency[edge.source_id].append((edge.target_id, edge))
            elif edge.edge_type is EdgeType.MEMBER_OF:
                memberships.append(edge)
            elif edge.edge_type is EdgeType.ASSIGNED_ROLE:
                group_role_edges[edge.source_id].append(edge)
        cycles = _detect_group_cycles(group_adjacency)
        if cycles:
            warnings.append(
                f"detected {len(cycles)} nested-group cycle(s); cycle edges were bounded"
            )

        membership_paths: dict[str, dict[str, tuple[GraphEdge, ...]]] = defaultdict(dict)
        for member_edge in sorted(memberships, key=lambda item: item.edge_id):
            actor = node_by_id[member_edge.source_id]
            if actor.node_type not in IDENTITY_TYPES:
                continue
            queue: deque[tuple[str, tuple[GraphEdge, ...]]] = deque(
                [(member_edge.target_id, (member_edge,))]
            )
            visited: set[str] = set()
            while queue:
                group_id, path = queue.popleft()
                if group_id in visited:
                    continue
                visited.add(group_id)
                membership_paths[actor.node_id][group_id] = path
                for parent_id, nesting_edge in sorted(group_adjacency.get(group_id, [])):
                    if parent_id not in visited:
                        queue.append((parent_id, (*path, nesting_edge)))

        for actor_id, group_paths in sorted(membership_paths.items()):
            actor = node_by_id[actor_id]
            for group_id, membership_path in sorted(group_paths.items()):
                for role_edge in sorted(
                    group_role_edges.get(group_id, []), key=lambda item: item.edge_id
                ):
                    role = node_by_id[role_edge.target_id]
                    raw_path = (*membership_path, role_edge)
                    if denied(actor_id, role.node_id, role_edge.scope):
                        continue
                    states = [eligible[edge.edge_id][1] for edge in raw_path]
                    state = (
                        ConditionState.UNKNOWN
                        if ConditionState.UNKNOWN in states
                        else ConditionState.TRUE
                    )
                    compiled = self._make_effective(
                        actor=actor,
                        target=role,
                        raw_edges=raw_path,
                        rule="nested_group_role_assignment",
                        capability=EdgeType.ASSIGNED_ROLE.value,
                        transition_type="GROUP_INHERITED_ROLE",
                        condition_state=state,
                    )
                    effective[compiled.edge_id] = compiled

        policy_attachments: dict[str, list[GraphEdge]] = defaultdict(list)
        policy_grants: dict[str, list[GraphEdge]] = defaultdict(list)
        for edge in eligible_edges:
            if edge.edge_type is EdgeType.POLICY_ATTACHED_TO:
                policy_attachments[edge.target_id].append(edge)
            elif node_by_id[edge.source_id].node_type is NodeType.POLICY and edge.edge_type in {
                EdgeType.GRANTS_PERMISSION,
                EdgeType.READS,
                EdgeType.WRITES,
                EdgeType.ADMINISTERS,
            }:
                policy_grants[edge.source_id].append(edge)
        for policy_id, attachments in sorted(policy_attachments.items()):
            for attachment in sorted(attachments, key=lambda item: item.edge_id):
                principals: list[tuple[GraphNode, tuple[GraphEdge, ...]]] = []
                principal = node_by_id[attachment.source_id]
                if principal.node_type in IDENTITY_TYPES or principal.node_type is NodeType.ROLE:
                    principals.append((principal, (attachment,)))
                elif principal.node_type is NodeType.GROUP:
                    principals.extend(
                        (node_by_id[actor_id], (*group_paths[principal.node_id], attachment))
                        for actor_id, group_paths in membership_paths.items()
                        if principal.node_id in group_paths
                    )
                for grant in sorted(
                    policy_grants.get(policy_id, []), key=lambda item: item.edge_id
                ):
                    target = node_by_id[grant.target_id]
                    for actor, prefix in principals:
                        if denied(actor.node_id, target.node_id, grant.scope):
                            continue
                        raw_path = (*prefix, grant)
                        states = [eligible[edge.edge_id][1] for edge in raw_path]
                        state = (
                            ConditionState.UNKNOWN
                            if ConditionState.UNKNOWN in states
                            else ConditionState.TRUE
                        )
                        compiled = self._make_effective(
                            actor=actor,
                            target=target,
                            raw_edges=raw_path,
                            rule="attached_policy_grant",
                            capability=grant.edge_type.value,
                            transition_type="POLICY_DERIVED_CAPABILITY",
                            condition_state=state,
                        )
                        effective[compiled.edge_id] = compiled

        inheritance_edges = [
            edge for edge in eligible_edges if edge.edge_type is EdgeType.INHERITS_FROM
        ]
        direct_permissions = [
            edge
            for edge in eligible_edges
            if edge.edge_type
            in {EdgeType.GRANTS_PERMISSION, EdgeType.READS, EdgeType.WRITES, EdgeType.ADMINISTERS}
        ]
        for inheritance in inheritance_edges:
            child = node_by_id[inheritance.source_id]
            for permission in direct_permissions:
                if permission.target_id != inheritance.target_id:
                    continue
                actor = node_by_id[permission.source_id]
                if denied(actor.node_id, child.node_id, permission.scope):
                    continue
                raw_path = (permission, inheritance)
                compiled = self._make_effective(
                    actor=actor,
                    target=child,
                    raw_edges=raw_path,
                    rule="inherited_parent_scope",
                    capability=permission.edge_type.value,
                    transition_type="INHERITED_SCOPE_CAPABILITY",
                    condition_state=(
                        ConditionState.UNKNOWN
                        if any(
                            eligible[edge.edge_id][1] is ConditionState.UNKNOWN for edge in raw_path
                        )
                        else ConditionState.TRUE
                    ),
                )
                effective[compiled.edge_id] = compiled

        return CompilationResult(
            effective_edges=tuple(sorted(effective.values(), key=lambda item: item.edge_id)),
            rejected_edges=tuple(
                sorted(rejected, key=lambda item: (item.raw_evidence_edge_ids, item.reason))
            ),
            group_cycles=cycles,
            warnings=tuple(warnings),
        )
