"""Verified structured and textual finding explanations."""

from graphtrust.schemas.findings import PathFinding

RELATIONSHIP_VERBS = {
    "MEMBER_OF": "is a member of",
    "GROUP_INHERITED_ROLE": "inherits role",
    "ASSIGNED_ROLE": "is assigned role",
    "ASSUMES_ROLE": "may assume",
    "CAN_IMPERSONATE": "may impersonate",
    "CAN_MODIFY": "may modify",
    "CAN_TRIGGER": "may trigger",
    "RUNS_AS": "runs as",
    "DEPLOYS_TO": "deploys to",
    "READS": "may read",
    "WRITES": "may write",
    "ADMINISTERS": "may administer",
    "POLICY_DERIVED_CAPABILITY": "receives policy-derived access to",
    "INHERITED_SCOPE_CAPABILITY": "inherits parent-scope access to",
}


def explanation_record(finding: PathFinding) -> dict[str, object]:
    """Generate a data-backed explanation without free-form model output."""
    steps = [
        {
            "position": step.position,
            "actor_before": step.actor_before,
            "verb": RELATIONSHIP_VERBS.get(step.transition_type, step.transition_type.lower()),
            "target": step.target_id,
            "capability": step.capability,
            "condition_state": step.condition_state.value,
            "raw_evidence_edge_ids": step.raw_evidence_edge_ids,
            "semantic_rule_id": step.semantic_rule_id,
        }
        for step in finding.path
    ]
    baseline_reasons = {
        method.value: (
            "detected this source-target authorization path"
            if detected
            else "did not retain this source-target authorization path under its declared scope"
        )
        for method, detected in finding.baseline_detection.items()
    }
    return {
        "finding_id": finding.finding_id,
        "source_identity_id": finding.source_identity_id,
        "source_apparent_privilege": finding.source_privilege_label.value,
        "target_asset_id": finding.target_asset_id,
        "ordered_path": steps,
        "score_decomposition": finding.risk.model_dump(mode="json"),
        "baseline_comparison": baseline_reasons,
        "uncertainty": {
            "search_complete": finding.search.search_complete,
            "truncation_reason": finding.search.truncation_reason,
            "caveats": finding.caveats,
        },
        "required_language": (
            "This is a potential authorization exposure path, not proof of exploitability. "
            "Weights are ordinal relative-risk parameters, not breach probabilities."
        ),
    }


def render_path_explanation(finding: PathFinding) -> str:
    path_text = " -> ".join(
        f"{step.actor_before} "
        f"{RELATIONSHIP_VERBS.get(step.transition_type, step.transition_type.lower())} "
        f"{step.target_id}"
        for step in finding.path
    )
    return (
        f"{finding.source_identity_id} has a potential authorization path to "
        f"{finding.target_asset_id}: {path_text}. Relative path risk "
        f"{finding.risk.path_risk:.6f}; not a calibrated incident probability."
    )
