"""Deterministic bounded top-K loopless path search with explicit budgets."""

import heapq
from dataclasses import dataclass
from itertools import count
from typing import Literal

from graphtrust.analysis.path_risk import edge_transition_cost
from graphtrust.graph.protocol import CapabilityGraphBackend, CapabilityPath
from graphtrust.schemas.conditions import ConditionState
from graphtrust.semantics.effective_access import EffectiveCapabilityEdge

WeightMode = Literal["typed", "untyped"]


@dataclass(frozen=True, slots=True)
class PathSearchResult:
    paths: tuple[CapabilityPath, ...]
    search_complete: bool
    truncation_reason: str | None
    expanded_states: int
    candidate_paths_considered: int


@dataclass(frozen=True, slots=True)
class _FrontierState:
    visited: frozenset[str]
    cost: float
    depth: int
    unknown_count: int


def _is_dominated(
    frontier: list[_FrontierState],
    candidate: _FrontierState,
) -> bool:
    return any(
        previous.visited <= candidate.visited
        and previous.cost <= candidate.cost
        and previous.depth <= candidate.depth
        and previous.unknown_count <= candidate.unknown_count
        and (
            previous.visited < candidate.visited
            or previous.cost < candidate.cost
            or previous.depth < candidate.depth
            or previous.unknown_count < candidate.unknown_count
        )
        for previous in frontier
    )


def top_k_loopless_paths(
    backend: CapabilityGraphBackend,
    source_id: str,
    target_id: str,
    *,
    maximum_depth: int = 8,
    top_k: int = 20,
    expansion_cap: int = 50_000,
    weight_mode: WeightMode = "typed",
) -> PathSearchResult:
    """Best-first loopless search, correct for nonnegative typed or unit costs."""
    reverse_distance = backend.reverse_reachable((target_id,), maximum_depth=maximum_depth)
    if source_id not in reverse_distance:
        return PathSearchResult((), True, None, 0, 0)

    serial = count()
    heap: list[
        tuple[
            float,
            tuple[str, ...],
            int,
            str,
            tuple[str, ...],
            tuple[EffectiveCapabilityEdge, ...],
        ]
    ] = [(0.0, (), next(serial), source_id, (source_id,), ())]
    frontier: dict[str, list[_FrontierState]] = {
        source_id: [_FrontierState(frozenset({source_id}), 0, 0, 0)]
    }
    results: list[CapabilityPath] = []
    expanded = 0
    candidates = 0

    while heap:
        cost_so_far, _, _, node_id, node_path, edge_path = heapq.heappop(heap)
        if node_id == target_id and edge_path:
            candidates += 1
            results.append(CapabilityPath(node_ids=node_path, edges=edge_path))
            if len(results) >= top_k:
                return PathSearchResult(tuple(results), True, None, expanded, candidates)
            continue
        if len(edge_path) >= maximum_depth:
            continue
        if expanded >= expansion_cap:
            return PathSearchResult(
                tuple(results),
                False,
                "per_source_target_expansion_cap",
                expanded,
                candidates,
            )
        expanded += 1
        for next_id, edge in backend.successors(node_id):
            if next_id in node_path or next_id not in reverse_distance:
                continue
            next_depth = len(edge_path) + 1
            if next_depth + reverse_distance[next_id] > maximum_depth:
                continue
            step_cost = 1.0 if weight_mode == "untyped" else edge_transition_cost(edge)
            next_cost = cost_so_far + step_cost
            next_edges = (*edge_path, edge)
            next_nodes = (*node_path, next_id)
            unknown_count = sum(
                item.condition_state is ConditionState.UNKNOWN for item in next_edges
            )
            state = _FrontierState(
                visited=frozenset(next_nodes),
                cost=next_cost,
                depth=next_depth,
                unknown_count=unknown_count,
            )
            node_frontier = frontier.setdefault(next_id, [])
            if _is_dominated(node_frontier, state):
                continue
            node_frontier[:] = [
                previous
                for previous in node_frontier
                if not (
                    state.visited <= previous.visited
                    and state.cost <= previous.cost
                    and state.depth <= previous.depth
                    and state.unknown_count <= previous.unknown_count
                    and (
                        state.visited < previous.visited
                        or state.cost < previous.cost
                        or state.depth < previous.depth
                        or state.unknown_count < previous.unknown_count
                    )
                )
            ]
            node_frontier.append(state)
            edge_ids = tuple(item.edge_id for item in next_edges)
            heapq.heappush(
                heap,
                (next_cost, edge_ids, next(serial), next_id, next_nodes, next_edges),
            )
    return PathSearchResult(tuple(results), True, None, expanded, candidates)
