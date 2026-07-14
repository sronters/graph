"""Risk-path choke-point diagnostics with provenance-aware coverage."""

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

import networkx as nx

from graphtrust.schemas.findings import PathFinding


@dataclass(frozen=True, slots=True)
class ChokePoint:
    raw_edge_id: str
    path_count: int
    distinct_sources: int
    distinct_targets: int
    covered_relative_exposure: float
    weighted_edge_betweenness: float
    marginal_exposure_reduction: float


@dataclass(frozen=True, slots=True)
class ChokePointReport:
    edges: tuple[ChokePoint, ...]
    projection_articulation_nodes: tuple[str, ...]
    directed_dominator_nodes: tuple[str, ...]


def analyze_choke_points(findings: Sequence[PathFinding]) -> ChokePointReport:
    """Calculate path coverage, betweenness, projection articulation, and dominators."""
    graph: nx.DiGraph[str] = nx.DiGraph()
    raw_to_transitions: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for finding in findings:
        for step in finding.path:
            graph.add_edge(step.actor_before, step.target_id, weight=1.0)
            for raw_id in step.raw_evidence_edge_ids:
                raw_to_transitions[raw_id].add((step.actor_before, step.target_id))
    edge_betweenness = (
        nx.edge_betweenness_centrality(graph, weight="weight", normalized=True)
        if graph.number_of_edges()
        else {}
    )
    articulation = (
        tuple(sorted(nx.articulation_points(graph.to_undirected())))
        if graph.number_of_nodes() > 1
        else ()
    )
    dominators: tuple[str, ...] = ()
    if findings:
        source = "__graphtrust_super_source__"
        sink = "__graphtrust_super_sink__"
        dominator_graph = graph.copy()
        for source_id in sorted({finding.source_identity_id for finding in findings}):
            dominator_graph.add_edge(source, source_id)
        for target_id in sorted({finding.target_asset_id for finding in findings}):
            dominator_graph.add_edge(target_id, sink)
        immediate = nx.immediate_dominators(dominator_graph, source)
        chain: list[str] = []
        current = sink
        while current in immediate and immediate[current] != current:
            current = immediate[current]
            if current not in {source, sink}:
                chain.append(current)
        dominators = tuple(sorted(chain))

    counts: Counter[str] = Counter()
    sources: dict[str, set[str]] = defaultdict(set)
    targets: dict[str, set[str]] = defaultdict(set)
    exposure: dict[str, float] = defaultdict(float)
    for finding in findings:
        evidence = {raw_id for step in finding.path for raw_id in step.raw_evidence_edge_ids}
        for edge_id in evidence:
            counts[edge_id] += 1
            sources[edge_id].add(finding.source_identity_id)
            targets[edge_id].add(finding.target_asset_id)
            exposure[edge_id] += finding.risk.path_risk
    values = (
        ChokePoint(
            raw_edge_id=edge_id,
            path_count=count,
            distinct_sources=len(sources[edge_id]),
            distinct_targets=len(targets[edge_id]),
            covered_relative_exposure=exposure[edge_id],
            weighted_edge_betweenness=max(
                (
                    edge_betweenness.get(transition, 0.0)
                    for transition in raw_to_transitions[edge_id]
                ),
                default=0.0,
            ),
            marginal_exposure_reduction=exposure[edge_id],
        )
        for edge_id, count in counts.items()
    )
    ranked = tuple(
        sorted(
            values,
            key=lambda item: (
                -item.marginal_exposure_reduction,
                -item.weighted_edge_betweenness,
                -item.distinct_sources,
                -item.distinct_targets,
                item.raw_edge_id,
            ),
        )
    )
    return ChokePointReport(ranked, articulation, dominators)


def rank_path_choke_points(findings: Sequence[PathFinding]) -> tuple[ChokePoint, ...]:
    """Rank removable evidence edges by retained path coverage and exposure."""
    return analyze_choke_points(findings).edges
