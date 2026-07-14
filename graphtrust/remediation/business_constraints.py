"""Mandatory workflow preservation checks."""

from dataclasses import dataclass

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
                paths = reduced.bounded_simple_paths(
                    source_id,
                    target_id,
                    maximum_depth=requirement.maximum_path_length,
                    path_cap=requirement.minimum_remaining_paths,
                )
                remaining += sum(
                    bool(path.edges)
                    and path.edges[-1].capability == requirement.required_capability
                    for path in paths
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
