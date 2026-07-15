"""Explainable identity-level Zero Trust Risk Index."""

import math
from collections import defaultdict
from collections.abc import Sequence

from graphtrust.graph.protocol import CapabilityGraphBackend
from graphtrust.schemas.findings import IdentityRiskScore, PathFinding
from graphtrust.schemas.nodes import IdentityStatus, NodeType


def _edge_disjoint_count(findings: Sequence[PathFinding]) -> int:
    used: set[str] = set()
    count = 0
    for finding in sorted(findings, key=lambda item: (-item.risk.path_risk, item.finding_id)):
        evidence = {raw_id for step in finding.path for raw_id in step.raw_evidence_edge_ids}
        if evidence.isdisjoint(used):
            used.update(evidence)
            count += 1
    return count


def calculate_identity_scores(
    backend: CapabilityGraphBackend,
    findings: Sequence[PathFinding],
    source_ids: Sequence[str],
    critical_asset_ids: Sequence[str],
    *,
    maximum_depth: int,
) -> tuple[IdentityRiskScore, ...]:
    """Calculate all five normalized components and retain full precision."""
    node_by_id = {node.node_id: node for node in backend.nodes()}
    criticality = {
        node_id: node_by_id[node_id].criticality
        for node_id in critical_asset_ids
        if node_id in node_by_id
    }
    total_criticality = sum(criticality.values()) or 1.0
    total_node_criticality = sum(node.criticality for node in node_by_id.values()) or 1.0
    findings_by_source: dict[str, list[PathFinding]] = defaultdict(list)
    for finding in findings:
        findings_by_source[finding.source_identity_id].append(finding)
    scores: list[IdentityRiskScore] = []
    for source_id in sorted(set(source_ids)):
        identity = node_by_id[source_id]
        reachable = backend.reachable((source_id,), maximum_depth=maximum_depth)
        critical_reach = (
            sum(
                criticality[node_id] * math.exp(-0.35 * reachable[node_id])
                for node_id in criticality
                if node_id in reachable
            )
            / total_criticality
        )
        source_findings = findings_by_source[source_id]
        best_path = max((finding.risk.path_risk for finding in source_findings), default=0.0)
        path_diversity = min(1.0, _edge_disjoint_count(source_findings) / 5.0)
        blast_radius = min(
            1.0,
            sum(node_by_id[node_id].criticality for node_id in reachable if node_id != source_id)
            / total_node_criticality,
        )
        unknown_steps = sum(
            step.condition_state.value == "UNKNOWN"
            for finding in source_findings
            for step in finding.path
        )
        total_steps = sum(len(finding.path) for finding in source_findings)
        control_weakness = (
            0.55 * (1.0 - identity.authentication_strength)
            + 0.20 * (identity.identity_status is IdentityStatus.DORMANT)
            + 0.15 * (identity.node_type is NodeType.EXTERNAL_IDENTITY)
            + 0.10 * (unknown_steps / total_steps if total_steps else 0.0)
        )
        control_weakness = max(0.0, min(1.0, control_weakness))
        ztri = 100.0 * (
            0.30 * critical_reach
            + 0.30 * best_path
            + 0.15 * path_diversity
            + 0.15 * blast_radius
            + 0.10 * control_weakness
        )
        scores.append(
            IdentityRiskScore(
                node_id=source_id,
                critical_reach=max(0.0, min(1.0, critical_reach)),
                best_path=best_path,
                path_diversity=path_diversity,
                blast_radius=blast_radius,
                control_weakness=control_weakness,
                ztri=max(0.0, min(100.0, ztri)),
            )
        )
    return tuple(sorted(scores, key=lambda item: (-item.ztri, item.node_id)))
