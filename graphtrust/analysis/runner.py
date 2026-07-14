"""Shared execution protocol for B0-B3 and GraphTrust."""

import hashlib
from dataclasses import dataclass, replace
from typing import Literal

from graphtrust.analysis.direct_baseline import is_direct_entitlement
from graphtrust.analysis.identity_risk import calculate_identity_scores
from graphtrust.analysis.native_scope_baseline import is_native_scope_edge
from graphtrust.analysis.path_risk import path_transition_cost, relative_path_risk, start_exposure
from graphtrust.analysis.paths import PathSearchResult, WeightMode, top_k_loopless_paths
from graphtrust.analysis.privileged_baseline import is_privileged_start
from graphtrust.analysis.reachability import SourceReachability
from graphtrust.analysis.untyped_baseline import untyped_rank_key
from graphtrust.graph.igraph_backend import IgraphBackend
from graphtrust.graph.networkx_backend import NetworkXBackend
from graphtrust.graph.protocol import CapabilityGraphBackend, CapabilityPath
from graphtrust.schemas.conditions import ConditionState
from graphtrust.schemas.findings import (
    AnalysisMethod,
    IdentityRiskScore,
    PathFinding,
    PathStep,
    RiskComponents,
    SearchMetadata,
)
from graphtrust.schemas.nodes import GraphNode, IdentityStatus, NodeType
from graphtrust.semantics.effective_access import EffectiveCapabilityEdge

IDENTITY_TYPES = frozenset(
    {
        NodeType.HUMAN_IDENTITY,
        NodeType.SERVICE_ACCOUNT,
        NodeType.WORKLOAD_IDENTITY,
        NodeType.EXTERNAL_IDENTITY,
    }
)

METHOD_LIMITATIONS: dict[AnalysisMethod, str] = {
    AnalysisMethod.DIRECT: (
        "B0 is deliberately narrow: it excludes group-derived, assumed-role, impersonation, "
        "pipeline-control, and multi-hop relationships."
    ),
    AnalysisMethod.PRIVILEGED: (
        "B1 traverses the graph but excludes low-apparent-privilege starting identities."
    ),
    AnalysisMethod.UNTYPED: (
        "B2 isolates reachability from type-aware ranking by using unit transition costs."
    ),
    AnalysisMethod.NATIVE_SCOPE: (
        "B3 resolves direct/group/scope access but excludes identity-control transitions."
    ),
    AnalysisMethod.GRAPHTRUST: (
        "GraphTrust reports bounded potential authorization paths; search truncation and unknown "
        "semantics remain explicit."
    ),
}


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    method: AnalysisMethod
    findings: tuple[PathFinding, ...]
    identity_scores: tuple[IdentityRiskScore, ...]
    reachability: tuple[SourceReachability, ...]
    search_complete: bool
    expanded_states: int
    candidate_paths_considered: int
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnalysisLimits:
    maximum_depth: int = 8
    top_k_per_source_target: int = 20
    top_k_per_source: int = 100
    global_path_cap: int = 250_000
    per_source_target_expansion_cap: int = 50_000


def _backend(
    backend_name: Literal["networkx", "igraph"],
    nodes: tuple[GraphNode, ...],
    edges: tuple[EffectiveCapabilityEdge, ...],
) -> CapabilityGraphBackend:
    return (
        NetworkXBackend(nodes, edges) if backend_name == "networkx" else IgraphBackend(nodes, edges)
    )


def _finding_id(
    method: AnalysisMethod,
    source_id: str,
    target_id: str,
    edge_ids: tuple[str, ...],
) -> str:
    material = "\0".join((method.value, source_id, target_id, *edge_ids))
    return "finding:" + hashlib.sha256(material.encode()).hexdigest()[:24]


def _to_finding(
    method: AnalysisMethod,
    path: CapabilityPath,
    source: GraphNode,
    target: GraphNode,
    search: PathSearchResult,
) -> PathFinding:
    transition_cost = path_transition_cost(path.edges)
    path_risk = relative_path_risk(source, target, path.edges)
    caveats = [
        "Relative risk parameters are ordinal assumptions, not calibrated breach probabilities."
    ]
    if any(edge.condition_state is ConditionState.UNKNOWN for edge in path.edges):
        caveats.append("One or more semantic conditions are unknown in this analysis mode.")
    if not search.search_complete:
        caveats.append(f"Path search truncated: {search.truncation_reason}")
    return PathFinding(
        finding_id=_finding_id(method, source.node_id, target.node_id, path.edge_ids),
        method=method,
        source_identity_id=source.node_id,
        source_privilege_label=source.privilege_label,
        target_asset_id=target.node_id,
        path=tuple(
            PathStep(
                position=index,
                actor_before=edge.actor_before,
                actor_after=edge.actor_after,
                target_id=edge.resource_or_identity_target,
                capability=edge.capability,
                transition_type=edge.transition_type,
                condition_state=edge.condition_state,
                relative_exploitability=edge.relative_exploitability,
                raw_evidence_edge_ids=edge.raw_evidence_edge_ids,
                semantic_rule_id=edge.semantic_rule_id,
            )
            for index, edge in enumerate(path.edges)
        ),
        risk=RiskComponents(
            criticality=target.criticality,
            start_exposure=start_exposure(source),
            transition_cost=transition_cost,
            path_risk=path_risk,
        ),
        search=SearchMetadata(
            search_complete=search.search_complete,
            truncation_reason=search.truncation_reason,
            expanded_states=search.expanded_states,
            candidate_paths_considered=search.candidate_paths_considered,
        ),
        caveats=tuple(caveats),
    )


def _method_edges(
    method: AnalysisMethod,
    edges: tuple[EffectiveCapabilityEdge, ...],
) -> tuple[EffectiveCapabilityEdge, ...]:
    if method is AnalysisMethod.DIRECT:
        return tuple(edge for edge in edges if is_direct_entitlement(edge))
    if method is AnalysisMethod.NATIVE_SCOPE:
        return tuple(edge for edge in edges if is_native_scope_edge(edge))
    return edges


def _candidate_sources(
    method: AnalysisMethod, nodes: tuple[GraphNode, ...]
) -> tuple[GraphNode, ...]:
    candidates = tuple(
        node
        for node in nodes
        if node.node_type in IDENTITY_TYPES and node.identity_status is IdentityStatus.ACTIVE
    )
    if method is AnalysisMethod.PRIVILEGED:
        return tuple(node for node in candidates if is_privileged_start(node))
    return candidates


def _run_method(
    method: AnalysisMethod,
    nodes: tuple[GraphNode, ...],
    edges: tuple[EffectiveCapabilityEdge, ...],
    critical_asset_ids: tuple[str, ...],
    *,
    limits: AnalysisLimits,
    backend_name: Literal["networkx", "igraph"],
) -> AnalysisResult:
    selected_edges = _method_edges(method, edges)
    backend = _backend(backend_name, nodes, selected_edges)
    node_by_id = {node.node_id: node for node in nodes}
    candidates = _candidate_sources(method, nodes)
    candidate_ids = {node.node_id for node in candidates}
    reverse = backend.reverse_reachable(
        critical_asset_ids,
        maximum_depth=(1 if method is AnalysisMethod.DIRECT else limits.maximum_depth),
    )
    source_ids = tuple(sorted(candidate_ids.intersection(reverse)))
    findings: list[PathFinding] = []
    reachability: list[SourceReachability] = []
    expanded_states = 0
    candidate_paths = 0
    search_complete = True
    warnings = [METHOD_LIMITATIONS[method]]
    depth = 1 if method is AnalysisMethod.DIRECT else limits.maximum_depth
    weight_mode: WeightMode = "untyped" if method is AnalysisMethod.UNTYPED else "typed"

    for source_id in source_ids:
        distances = backend.reachable((source_id,), maximum_depth=depth)
        targets = tuple(sorted(set(critical_asset_ids).intersection(distances)))
        if not targets:
            continue
        reachability.append(
            SourceReachability(
                source_id=source_id,
                reachable_critical_assets=targets,
                minimum_depth=min(distances[target_id] for target_id in targets),
            )
        )
        source_findings: list[PathFinding] = []
        for target_id in targets:
            remaining_source = limits.top_k_per_source - len(source_findings)
            remaining_global = limits.global_path_cap - len(findings) - len(source_findings)
            if remaining_source <= 0 or remaining_global <= 0:
                search_complete = False
                warnings.append("Configured per-source or global path cap was reached.")
                break
            search = top_k_loopless_paths(
                backend,
                source_id,
                target_id,
                maximum_depth=depth,
                top_k=min(limits.top_k_per_source_target, remaining_source, remaining_global),
                expansion_cap=limits.per_source_target_expansion_cap,
                weight_mode=weight_mode,
            )
            expanded_states += search.expanded_states
            candidate_paths += search.candidate_paths_considered
            search_complete = search_complete and search.search_complete
            source_findings.extend(
                _to_finding(
                    method,
                    path,
                    node_by_id[source_id],
                    node_by_id[target_id],
                    search,
                )
                for path in search.paths
            )
        if method is AnalysisMethod.UNTYPED:
            source_findings.sort(key=untyped_rank_key)
        else:
            source_findings.sort(key=lambda finding: (-finding.risk.path_risk, finding.finding_id))
        findings.extend(source_findings[: limits.top_k_per_source])
        if len(findings) >= limits.global_path_cap:
            search_complete = False
            break

    if method is AnalysisMethod.UNTYPED:
        findings.sort(key=untyped_rank_key)
    else:
        findings.sort(key=lambda finding: (-finding.risk.path_risk, finding.finding_id))
    findings = findings[: limits.global_path_cap]
    scores = calculate_identity_scores(
        backend,
        findings,
        source_ids,
        critical_asset_ids,
        maximum_depth=depth,
    )
    return AnalysisResult(
        method=method,
        findings=tuple(findings),
        identity_scores=scores,
        reachability=tuple(reachability),
        search_complete=search_complete,
        expanded_states=expanded_states,
        candidate_paths_considered=candidate_paths,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _annotate_baseline_detection(
    results: dict[AnalysisMethod, AnalysisResult],
) -> dict[AnalysisMethod, AnalysisResult]:
    graphtrust = results.get(AnalysisMethod.GRAPHTRUST)
    if graphtrust is None:
        return results
    baseline_pairs = {
        method: {
            (finding.source_identity_id, finding.target_asset_id) for finding in result.findings
        }
        for method, result in results.items()
        if method is not AnalysisMethod.GRAPHTRUST
    }
    annotated = tuple(
        finding.model_copy(
            update={
                "baseline_detection": {
                    method: (finding.source_identity_id, finding.target_asset_id) in pairs
                    for method, pairs in baseline_pairs.items()
                }
            }
        )
        for finding in graphtrust.findings
    )
    results[AnalysisMethod.GRAPHTRUST] = replace(graphtrust, findings=annotated)
    return results


def run_analysis_methods(
    nodes: tuple[GraphNode, ...],
    effective_edges: tuple[EffectiveCapabilityEdge, ...],
    critical_asset_ids: tuple[str, ...],
    *,
    methods: tuple[AnalysisMethod, ...] = tuple(AnalysisMethod),
    limits: AnalysisLimits | None = None,
    backend_name: Literal["networkx", "igraph"] = "networkx",
) -> dict[AnalysisMethod, AnalysisResult]:
    """Run every method against the same truth-hidden nodes, edges, and targets."""
    resolved_limits = limits or AnalysisLimits()
    results = {
        method: _run_method(
            method,
            nodes,
            effective_edges,
            critical_asset_ids,
            limits=resolved_limits,
            backend_name=backend_name,
        )
        for method in methods
    }
    return _annotate_baseline_detection(results)
