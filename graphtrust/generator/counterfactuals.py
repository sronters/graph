"""Paired truth-remediation transformations."""

from graphtrust.generator.risk_injection import RiskInjectionResult


def apply_truth_remediation(injected: RiskInjectionResult) -> RiskInjectionResult:
    """Deactivate scenario-authored minimal edges while retaining truth provenance."""
    removals = set(injected.intended_removals)
    edges = [
        {**edge, "active": False} if edge["edge_id"] in removals else dict(edge)
        for edge in injected.edges
    ]
    return RiskInjectionResult(
        edges=edges,
        conditions=[dict(condition) for condition in injected.conditions],
        truth_paths=[dict(path) for path in injected.truth_paths],
        truth_scenarios=[dict(scenario) for scenario in injected.truth_scenarios],
        intended_removals=injected.intended_removals,
    )
