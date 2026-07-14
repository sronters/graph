"""Dataset coherence checks and structural quality summaries."""

import json
from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import Any

import igraph as ig  # type: ignore[import-untyped]
import numpy as np

from graphtrust.generator.models import GenerationState
from graphtrust.generator.resources import ResourceCatalog


def _group_cycles(edges: Sequence[dict[str, object]]) -> tuple[tuple[str, ...], ...]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge["edge_type"] == "NESTED_IN" and edge["active"]:
            adjacency[str(edge["source_id"])].append(str(edge["target_id"]))
    active: set[str] = set()
    complete: set[str] = set()
    stack: list[str] = []
    cycles: set[tuple[str, ...]] = set()

    def visit(node_id: str) -> None:
        if node_id in complete:
            return
        if node_id in active:
            start = stack.index(node_id)
            cycles.add(tuple([*stack[start:], node_id]))
            return
        active.add(node_id)
        stack.append(node_id)
        for target_id in adjacency.get(node_id, []):
            visit(target_id)
        stack.pop()
        active.remove(node_id)
        complete.add(node_id)

    for node_id in sorted(adjacency):
        visit(node_id)
    return tuple(sorted(cycles))


def _nesting_depth(edges: Sequence[dict[str, object]]) -> int:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge["edge_type"] == "NESTED_IN" and edge["active"]:
            adjacency[str(edge["source_id"])].append(str(edge["target_id"]))
    cache: dict[str, int] = {}

    def depth(node_id: str, visiting: frozenset[str]) -> int:
        if node_id in visiting:
            return 0
        if node_id in cache:
            return cache[node_id]
        value = 0
        if adjacency.get(node_id):
            value = 1 + max(depth(target, visiting | {node_id}) for target in adjacency[node_id])
        cache[node_id] = value
        return value

    return max((depth(node_id, frozenset()) for node_id in adjacency), default=0)


def _component_counts(
    nodes: Sequence[dict[str, object]], edges: Sequence[dict[str, object]]
) -> tuple[int, int]:
    node_index = {str(node["node_id"]): index for index, node in enumerate(nodes)}
    graph_edges = [
        (node_index[str(edge["source_id"])], node_index[str(edge["target_id"])])
        for edge in edges
        if edge["active"]
    ]
    graph = ig.Graph(n=len(nodes), edges=graph_edges, directed=True)
    weak = len(graph.connected_components(mode="weak"))
    strong = len(graph.connected_components(mode="strong"))
    return weak, strong


def build_quality_report(
    state: GenerationState,
    resources: ResourceCatalog,
    *,
    variant: str,
    edges: Sequence[dict[str, object]],
    truth_scenarios: Sequence[dict[str, object]],
    clean_edge_count: int,
    condition_count: int,
    intended_removals: Sequence[str] = (),
) -> dict[str, Any]:
    """Validate coherence and emit deterministic structural summaries."""
    errors: list[str] = []
    warnings: list[str] = []
    node_ids = {str(node["node_id"]) for node in state.nodes}
    edge_ids = [str(edge["edge_id"]) for edge in edges]
    if len(node_ids) != len(state.nodes):
        errors.append("node identifier collision")
    if len(set(edge_ids)) != len(edge_ids):
        errors.append("edge identifier collision")
    orphan_edges = [
        edge_id
        for edge_id, edge in zip(edge_ids, edges, strict=True)
        if str(edge["source_id"]) not in node_ids or str(edge["target_id"]) not in node_ids
    ]
    if orphan_edges:
        errors.append(f"orphan edges: {orphan_edges[:5]}")

    memberships = {
        str(edge["source_id"])
        for edge in edges
        if edge["edge_type"] == "MEMBER_OF" and edge["active"]
    }
    active_without_team = [
        str(node["node_id"])
        for node in state.nodes
        if node["node_type"] == "HUMAN_IDENTITY"
        and node["identity_status"] == "ACTIVE"
        and (
            str(node["node_id"]) not in memberships
            or not json.loads(str(node["tags_json"])).get("team_id")
        )
    ]
    if active_without_team:
        errors.append(f"active humans without team membership: {active_without_team[:5]}")

    ownerless_applications = [
        str(node["node_id"])
        for node in state.nodes
        if node["node_type"] == "APPLICATION" and node["owner_node_id"] is None
    ]
    if ownerless_applications:
        errors.append(f"applications without owners: {ownerless_applications[:5]}")

    execution_sources = {
        str(edge["source_id"])
        for edge in edges
        if edge["edge_type"] == "RUNS_AS" and edge["active"]
    }
    production_without_identity = [
        pipeline
        for pipeline in resources.by_type["PIPELINE"]
        if state.node_by_id[pipeline]["environment"] == "PROD" and pipeline not in execution_sources
    ]
    if production_without_identity:
        errors.append(
            f"production pipelines without execution identity: {production_without_identity[:5]}"
        )

    protected_targets = {
        target
        for requirement in state.protected_requirements
        for target in json.loads(str(requirement["target_set_json"]))
    }
    missing_protected_route = set(resources.critical_assets) - protected_targets
    if missing_protected_route:
        errors.append(
            f"critical assets without protected route: {sorted(missing_protected_route)[:5]}"
        )

    disabled_nodes = {
        str(node["node_id"]) for node in state.nodes if node["identity_status"] == "DISABLED"
    }
    disabled_protected = [
        str(edge["edge_id"])
        for edge in edges
        if edge["protected"] and str(edge["source_id"]) in disabled_nodes
    ]
    if disabled_protected:
        errors.append(f"disabled identities on protected workflows: {disabled_protected[:5]}")

    human_ids = set(state.nodes_by_type["HUMAN_IDENTITY"])
    direct_privileged_sources = {
        str(edge["source_id"])
        for edge in edges
        if edge["edge_type"] == "ASSIGNED_ROLE" and str(edge["source_id"]) in human_ids
    }
    direct_privileged_share = len(direct_privileged_sources) / state.spec.humans
    if direct_privileged_share > float(state.config["direct_privilege_max_share"]):
        errors.append("direct human privilege share exceeds profile maximum")

    cycles = _group_cycles(edges)
    if cycles:
        errors.append(f"unexpected group nesting cycles: {cycles[:3]}")

    node_type_counts = Counter(str(node["node_type"]) for node in state.nodes)
    edge_type_counts = Counter(str(edge["edge_type"]) for edge in edges)
    in_degree = Counter(str(edge["target_id"]) for edge in edges if edge["active"])
    out_degree = Counter(str(edge["source_id"]) for edge in edges if edge["active"])
    degree_values = np.array(
        [in_degree[node_id] + out_degree[node_id] for node_id in sorted(node_ids)],
        dtype=np.int64,
    )
    weak_components, strong_components = _component_counts(state.nodes, edges)
    family_coverage = sorted(
        {
            str(scenario["family"])
            for scenario in truth_scenarios
            if not bool(scenario["is_hard_negative"])
        }
    )
    condition_counts = Counter(
        "CONDITIONAL" if edge["effect"] == "CONDITIONAL" else str(edge["effect"]) for edge in edges
    )
    status_counts = Counter(str(node["identity_status"]) for node in state.nodes)
    if variant == "clean" and truth_scenarios:
        errors.append("clean dataset contains scenario truth")
    if variant != "clean" and not truth_scenarios:
        warnings.append("injected variant has no scenarios")
    removal_set = set(intended_removals)

    return {
        "schema_version": "1.0",
        "benchmark": "SEIB-2026",
        "dataset_variant": variant,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "nodes": len(state.nodes),
            "edges": len(edges),
            "active_edges": sum(bool(edge["active"]) for edge in edges),
            "conditions": condition_count,
            "critical_assets": len(resources.critical_assets),
            "truth_scenarios": len(truth_scenarios),
        },
        "node_type_counts": dict(sorted(node_type_counts.items())),
        "edge_type_counts": dict(sorted(edge_type_counts.items())),
        "identity_status_counts": dict(sorted(status_counts.items())),
        "condition_effect_counts": dict(sorted(condition_counts.items())),
        "degree_distribution": {
            "median": float(np.quantile(degree_values, 0.5)),
            "p95": float(np.quantile(degree_values, 0.95)),
            "p99": float(np.quantile(degree_values, 0.99)),
            "maximum": int(degree_values.max(initial=0)),
        },
        "group_nesting_depth": _nesting_depth(edges),
        "connected_components": weak_components,
        "strongly_connected_components": strong_components,
        "orphan_edge_count": len(orphan_edges),
        "direct_privileged_human_share": direct_privileged_share,
        "scenario_family_coverage": family_coverage,
        "paired_structural_diff": {
            "edge_count_delta": len(edges) - clean_edge_count,
            "intended_remediation_edge_ids": sorted(intended_removals),
            "inactive_intended_removals": sum(
                not bool(edge["active"]) for edge in edges if edge["edge_id"] in removal_set
            ),
        },
    }
