"""Shared raw-evidence remediation problem model."""

import hashlib
from dataclasses import dataclass

from graphtrust.graph.protocol import CapabilityGraphBackend
from graphtrust.schemas.edges import GraphEdge
from graphtrust.schemas.findings import PathFinding
from graphtrust.schemas.nodes import GraphNode
from graphtrust.schemas.remediation import BusinessRequirement


@dataclass(frozen=True, slots=True)
class DangerousPath:
    path_id: str
    raw_edge_ids: frozenset[str]
    relative_exposure: float


@dataclass(frozen=True, slots=True)
class RemediationProblem:
    backend: CapabilityGraphBackend
    raw_edges: tuple[GraphEdge, ...]
    findings: tuple[PathFinding, ...]
    requirements: tuple[BusinessRequirement, ...] = ()

    @property
    def raw_edge_by_id(self) -> dict[str, GraphEdge]:
        return {edge.edge_id: edge for edge in self.raw_edges}

    @property
    def node_by_id(self) -> dict[str, GraphNode]:
        return {node.node_id: node for node in self.backend.nodes()}

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(sorted({finding.source_identity_id for finding in self.findings}))

    @property
    def target_ids(self) -> tuple[str, ...]:
        return tuple(sorted({finding.target_asset_id for finding in self.findings}))

    def removable_edges(self) -> dict[str, GraphEdge]:
        return {
            edge.edge_id: edge
            for edge in self.raw_edges
            if edge.removable and not edge.protected and edge.active
        }

    def dangerous_paths(self) -> tuple[DangerousPath, ...]:
        return tuple(
            DangerousPath(
                path_id=finding.finding_id,
                raw_edge_ids=frozenset(
                    raw_id for step in finding.path for raw_id in step.raw_evidence_edge_ids
                ),
                relative_exposure=finding.risk.path_risk,
            )
            for finding in self.findings
        )


def stable_plan_id(solver: str, removed_edge_ids: tuple[str, ...]) -> str:
    material = "\0".join((solver, *sorted(removed_edge_ids)))
    return "plan:" + hashlib.sha256(material.encode()).hexdigest()[:24]
