"""Mandatory workflow preservation checks."""

from dataclasses import dataclass

from graphtrust.graph.protocol import CapabilityGraphBackend
from graphtrust.remediation.problem import RemediationProblem
from graphtrust.remediation.verification import backend_without_raw_edges


@dataclass(frozen=True, slots=True)
class RequirementResult:
    requirement_id: str
    valid: bool
    remaining_paths: int
    required_paths: int


@dataclass(frozen=True, slots=True)
class BusinessVerification:
    valid: bool
    requirements: tuple[RequirementResult, ...]


def _count_required_capability_paths(
    backend: CapabilityGraphBackend,
    source_id: str,
    target_id: str,
    *,
    required_capability: str,
    maximum_path_length: int,
    required_paths: int,
) -> int:
    """Count matching bounded simple paths without letting distractor paths consume the cap.

    ``bounded_simple_paths(..., path_cap=n)`` caps all source-to-target paths before a
    caller can filter by the terminal capability. Realistic IAM graphs often contain
    several parallel routes to one asset, so a non-business route could previously hide
    a valid protected route. This traversal applies the capability predicate at the
    target and stops as soon as the requirement is satisfied.
    """
    if required_paths <= 0:
        return 0
    reverse_distance = backend.reverse_reachable((target_id,), maximum_depth=maximum_path_length)
    if source_id not in reverse_distance:
        return 0
    remaining = 0
    stack: list[tuple[str, tuple[str, ...], int]] = [(source_id, (source_id,), 0)]
    while stack and remaining < required_paths:
        node_id, node_path, depth = stack.pop()
        if depth >= maximum_path_length:
            continue
        for next_id, edge in reversed(backend.successors(node_id)):
            if next_id in node_path:
                continue
            next_depth = depth + 1
            distance_to_target = reverse_distance.get(next_id)
            if distance_to_target is None or next_depth + distance_to_target > maximum_path_length:
                continue
            if next_id == target_id:
                if edge.capability == required_capability:
                    remaining += 1
                    if remaining >= required_paths:
                        break
                continue
            if next_depth < maximum_path_length:
                stack.append((next_id, (*node_path, next_id), next_depth))
    return remaining


def verify_business_requirements(
    problem: RemediationProblem,
    removed_raw_edge_ids: tuple[str, ...],
) -> BusinessVerification:
    """Verify each protected workflow on the counterfactual graph."""
    reduced = backend_without_raw_edges(problem.backend, removed_raw_edge_ids)
    results: list[RequirementResult] = []
    for requirement in problem.requirements:
        remaining = 0
        for source_id in sorted(requirement.source_set):
            for target_id in sorted(requirement.target_set):
                remaining += _count_required_capability_paths(
                    reduced,
                    source_id,
                    target_id,
                    required_capability=requirement.required_capability,
                    maximum_path_length=requirement.maximum_path_length,
                    required_paths=requirement.minimum_remaining_paths - remaining,
                )
                if remaining >= requirement.minimum_remaining_paths:
                    break
            if remaining >= requirement.minimum_remaining_paths:
                break
        results.append(
            RequirementResult(
                requirement_id=requirement.requirement_id,
                valid=remaining >= requirement.minimum_remaining_paths,
                remaining_paths=remaining,
                required_paths=requirement.minimum_remaining_paths,
            )
        )
    return BusinessVerification(
        valid=all(result.valid for result in results),
        requirements=tuple(results),
    )
