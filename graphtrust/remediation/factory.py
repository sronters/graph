"""Reconstruct remediation inputs from one truth-hidden canonical dataset."""

import json
from pathlib import Path

from graphtrust.analysis.pipeline import analyze_bundle
from graphtrust.data import read_dataset
from graphtrust.graph.networkx_backend import NetworkXBackend
from graphtrust.remediation.problem import RemediationProblem
from graphtrust.schemas.findings import AnalysisMethod
from graphtrust.schemas.remediation import BusinessRequirement
from graphtrust.settings import ProjectConfig


def build_remediation_problem(dataset_path: Path, config: ProjectConfig) -> RemediationProblem:
    """Compile and analyze without truth, then attach protected business requirements."""
    bundle = read_dataset(dataset_path)
    analysis = analyze_bundle(bundle, config, (AnalysisMethod.GRAPHTRUST,))
    requirements = tuple(
        BusinessRequirement(
            requirement_id=str(row["requirement_id"]),
            source_set=frozenset(json.loads(str(row["source_set_json"]))),
            target_set=frozenset(json.loads(str(row["target_set_json"]))),
            required_capability=str(row["required_capability"]),
            minimum_remaining_paths=int(row["minimum_remaining_paths"]),
            maximum_path_length=int(row["maximum_path_length"]),
            priority=int(row["priority"]),
        )
        for row in bundle.protected_requirements.iter_rows(named=True)
    )
    return RemediationProblem(
        backend=NetworkXBackend(analysis.records.nodes, analysis.compilation.effective_edges),
        raw_edges=analysis.records.edges,
        findings=analysis.results[AnalysisMethod.GRAPHTRUST].findings,
        requirements=requirements,
    )
