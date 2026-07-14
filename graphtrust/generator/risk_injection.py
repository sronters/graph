"""Deterministic labeled risk scenarios and blocked hard negatives."""

import json
from dataclasses import dataclass
from datetime import timedelta
from typing import cast

from graphtrust.generator.models import GenerationState, stable_json
from graphtrust.generator.resources import ResourceCatalog

SCENARIO_FAMILIES = (
    "dormant_contractor_nested_deployment_group",
    "developer_indirect_production_role_assumption",
    "ci_pipeline_overprivileged_service_account",
    "workload_impersonates_privileged_service_account",
    "broad_cross_tenant_trust",
    "legacy_group_nested_into_privileged_group",
    "repository_maintainer_controls_production_pipeline",
    "application_owner_modifies_critical_role_binding",
    "external_identity_federated_group_chain",
    "shared_service_account_cross_department_bridge",
    "staging_identity_inherits_production_scope",
    "edge_disjoint_low_severity_paths",
)


@dataclass(frozen=True, slots=True)
class RiskInjectionResult:
    edges: list[dict[str, object]]
    conditions: list[dict[str, object]]
    truth_paths: list[dict[str, object]]
    truth_scenarios: list[dict[str, object]]
    intended_removals: tuple[str, ...]


def _append_edge(
    edges: list[dict[str, object]],
    nodes: dict[str, dict[str, object]],
    *,
    edge_id: str,
    source_id: str,
    target_id: str,
    edge_type: str,
    effect: str = "ALLOW",
    condition_id: str | None = None,
    active: bool = True,
    valid_until: object = None,
) -> str:
    source = nodes[source_id]
    edges.append(
        {
            "edge_id": edge_id,
            "source_id": source_id,
            "target_id": target_id,
            "edge_type": edge_type,
            "provider": source["provider"],
            "effect": effect,
            "scope": target_id,
            "condition_id": condition_id,
            "direct": True,
            "derived": False,
            "derivation_rule": None,
            "confidence": 1.0,
            "relative_exploitability": 0.82,
            "business_removal_cost": 0.75,
            "removable": True,
            "protected": False,
            "active": active,
            "valid_from": None,
            "valid_until": valid_until,
            "source_artifact": "seib-2026-generator",
        }
    )
    return edge_id


def _pools(state: GenerationState) -> dict[str, list[str]]:
    pools = {name: list(values) for name, values in state.nodes_by_type.items()}
    pools["ACTIVE_HUMAN"] = [
        node_id
        for node_id in pools["HUMAN_IDENTITY"]
        if state.node_by_id[node_id]["identity_status"] == "ACTIVE"
        and state.node_by_id[node_id]["privilege_label"] in {"LOW", "MEDIUM"}
    ]
    pools["DORMANT_HUMAN"] = [
        node_id
        for node_id in pools["HUMAN_IDENTITY"]
        if state.node_by_id[node_id]["identity_status"] == "DORMANT"
    ]
    pools["DISABLED_IDENTITY"] = [
        node_id
        for node_id in (
            *pools["HUMAN_IDENTITY"],
            *pools["SERVICE_ACCOUNT"],
        )
        if state.node_by_id[node_id]["identity_status"] == "DISABLED"
    ]
    return pools


def _path_definitions(
    pools: dict[str, list[str]], critical_assets: tuple[str, ...]
) -> list[list[tuple[list[str], list[str]]]]:
    def pick(name: str, index: int) -> str:
        values = pools[name]
        return values[index % len(values)]

    definitions: list[list[tuple[list[str], list[str]]]] = [
        [
            (
                [
                    pick("DORMANT_HUMAN", 0),
                    pick("GROUP", 0),
                    pick("GROUP", 1),
                    pick("ROLE", 0),
                    critical_assets[0 % len(critical_assets)],
                ],
                ["MEMBER_OF", "NESTED_IN", "ASSIGNED_ROLE", "ADMINISTERS"],
            )
        ],
        [
            (
                [
                    pick("ACTIVE_HUMAN", 1),
                    pick("ROLE", 1),
                    critical_assets[1 % len(critical_assets)],
                ],
                ["ASSUMES_ROLE", "ADMINISTERS"],
            )
        ],
        [
            (
                [
                    pick("ACTIVE_HUMAN", 2),
                    pick("REPOSITORY", 0),
                    pick("PIPELINE", 0),
                    pick("SERVICE_ACCOUNT", 0),
                    critical_assets[2 % len(critical_assets)],
                ],
                ["CAN_MODIFY", "CAN_TRIGGER", "RUNS_AS", "WRITES"],
            )
        ],
        [
            (
                [
                    pick("WORKLOAD_IDENTITY", 0),
                    pick("SERVICE_ACCOUNT", 1),
                    critical_assets[3 % len(critical_assets)],
                ],
                ["CAN_IMPERSONATE", "ADMINISTERS"],
            )
        ],
        [
            (
                [
                    pick("EXTERNAL_IDENTITY", 0),
                    pick("ROLE", 2),
                    critical_assets[4 % len(critical_assets)],
                ],
                ["FEDERATES_TO", "ADMINISTERS"],
            )
        ],
        [
            (
                [
                    pick("DORMANT_HUMAN", 1),
                    pick("GROUP", 2),
                    pick("ROLE", 3),
                    critical_assets[5 % len(critical_assets)],
                ],
                ["MEMBER_OF", "ASSIGNED_ROLE", "ADMINISTERS"],
            )
        ],
        [
            (
                [
                    pick("ACTIVE_HUMAN", 3),
                    pick("REPOSITORY", 1),
                    pick("PIPELINE", 1),
                    pick("WORKLOAD_IDENTITY", 1),
                    critical_assets[6 % len(critical_assets)],
                ],
                ["CAN_MODIFY", "CAN_TRIGGER", "RUNS_AS", "DEPLOYS_TO"],
            )
        ],
        [
            (
                [
                    pick("ACTIVE_HUMAN", 4),
                    pick("APPLICATION", 0),
                    pick("ROLE", 4),
                    critical_assets[7 % len(critical_assets)],
                ],
                ["MANAGES", "CAN_MODIFY", "ADMINISTERS"],
            )
        ],
        [
            (
                [
                    pick("EXTERNAL_IDENTITY", 1),
                    pick("GROUP", 3),
                    pick("ROLE", 5),
                    critical_assets[8 % len(critical_assets)],
                ],
                ["MEMBER_OF", "ASSIGNED_ROLE", "READS"],
            )
        ],
        [
            (
                [
                    pick("SERVICE_ACCOUNT", 2),
                    pick("APPLICATION", 1),
                    critical_assets[9 % len(critical_assets)],
                ],
                ["MANAGES", "READS"],
            )
        ],
        [
            (
                [
                    pick("WORKLOAD_IDENTITY", 2),
                    pick("ROLE", 6),
                    critical_assets[10 % len(critical_assets)],
                ],
                ["ASSIGNED_ROLE", "ADMINISTERS"],
            )
        ],
        [
            (
                [
                    pick("ACTIVE_HUMAN", 5),
                    pick("ROLE", 7),
                    critical_assets[11 % len(critical_assets)],
                ],
                ["ASSUMES_ROLE", "READS"],
            ),
            (
                [
                    pick("ACTIVE_HUMAN", 5),
                    pick("ROLE", 8),
                    critical_assets[11 % len(critical_assets)],
                ],
                ["ASSUMES_ROLE", "READS"],
            ),
        ],
    ]
    return definitions


def _add_hard_negative(
    state: GenerationState,
    family_index: int,
    edges: list[dict[str, object]],
    conditions: list[dict[str, object]],
    pools: dict[str, list[str]],
    target_id: str,
) -> tuple[str, str]:
    mode = family_index % 5
    scenario_id = f"HN-{family_index + 1:02d}-{state.seed}"
    start_pool = pools["ACTIVE_HUMAN"]
    start_id = start_pool[(family_index + 40) % len(start_pool)]
    edge_id = f"edge:hard-negative:{state.seed}:{family_index + 1:02d}:allow"
    if mode == 0:
        condition_id = f"condition:hard-negative:{state.seed}:{family_index + 1:02d}"
        conditions.append(
            {
                "condition_id": condition_id,
                "expression_json": stable_json(
                    {
                        "operator": "LEAF",
                        "operand": "ENVIRONMENT",
                        "comparator": "EQ",
                        "expected": "IMPOSSIBLE_ENVIRONMENT",
                        "children": [],
                    }
                ),
                "source_text": "hard negative: false environment condition",
            }
        )
        _append_edge(
            edges,
            state.node_by_id,
            edge_id=edge_id,
            source_id=start_id,
            target_id=target_id,
            edge_type="READS",
            effect="CONDITIONAL",
            condition_id=condition_id,
        )
        reason = "false_condition"
    elif mode == 1:
        _append_edge(
            edges,
            state.node_by_id,
            edge_id=edge_id,
            source_id=start_id,
            target_id=target_id,
            edge_type="READS",
            valid_until=state.generated_at - timedelta(days=1),
        )
        reason = "expired_assignment"
    elif mode == 2:
        _append_edge(
            edges,
            state.node_by_id,
            edge_id=edge_id,
            source_id=start_id,
            target_id=target_id,
            edge_type="READS",
            active=False,
        )
        reason = "inactive_relationship"
    elif mode == 3:
        _append_edge(
            edges,
            state.node_by_id,
            edge_id=edge_id,
            source_id=start_id,
            target_id=target_id,
            edge_type="READS",
        )
        _append_edge(
            edges,
            state.node_by_id,
            edge_id=f"edge:hard-negative:{state.seed}:{family_index + 1:02d}:deny",
            source_id=start_id,
            target_id=target_id,
            edge_type="DENIES",
            effect="DENY",
        )
        reason = "explicit_deny"
    else:
        disabled = pools["DISABLED_IDENTITY"]
        if disabled:
            start_id = disabled[family_index % len(disabled)]
        _append_edge(
            edges,
            state.node_by_id,
            edge_id=edge_id,
            source_id=start_id,
            target_id=target_id,
            edge_type="READS",
        )
        reason = "disabled_identity"
    return scenario_id, stable_json({"start_id": start_id, "blocked_reason": reason})


def inject_risk_scenarios(
    state: GenerationState,
    resources: ResourceCatalog,
    *,
    family_count: int,
) -> RiskInjectionResult:
    """Clone clean relationships and inject deterministic positive/negative scenarios."""
    edges = [dict(edge) for edge in state.edges]
    conditions = [dict(condition) for condition in state.conditions]
    truth_paths: list[dict[str, object]] = []
    truth_scenarios: list[dict[str, object]] = []
    intended_removals: list[str] = []
    pools = _pools(state)
    definitions = _path_definitions(pools, resources.critical_assets)

    for family_index, paths in enumerate(definitions[:family_count]):
        scenario_id = f"S{family_index + 1:02d}-{state.seed}"
        scenario_edge_ids: list[str] = []
        path_ids: list[str] = []
        start_ids: list[str] = []
        target_ids: list[str] = []
        removal_candidates: list[str] = []
        for path_index, (node_path, edge_types) in enumerate(paths):
            edge_ids: list[str] = []
            for step, edge_type in enumerate(edge_types):
                edge_id = f"edge:risk:{state.seed}:{family_index + 1:02d}:{path_index}:{step}"
                _append_edge(
                    edges,
                    state.node_by_id,
                    edge_id=edge_id,
                    source_id=node_path[step],
                    target_id=node_path[step + 1],
                    edge_type=edge_type,
                )
                edge_ids.append(edge_id)
            path_id = f"path:{scenario_id}:{path_index}"
            severity = round(0.52 + 0.035 * family_index + 0.02 * path_index, 6)
            truth_paths.append(
                {
                    "path_id": path_id,
                    "scenario_id": scenario_id,
                    "source_id": node_path[0],
                    "target_id": node_path[-1],
                    "edge_ids_json": stable_json(edge_ids),
                    "severity": severity,
                    "expected_detector_scope": (
                        "native_scope" if family_index in {0, 5, 8} else "graphtrust"
                    ),
                    "semantic_signature_json": stable_json(edge_types),
                }
            )
            path_ids.append(path_id)
            start_ids.append(node_path[0])
            target_ids.append(node_path[-1])
            scenario_edge_ids.extend(edge_ids)
            removal_candidates.append(edge_ids[0])
        intended_removals.extend(removal_candidates)
        truth_scenarios.append(
            {
                "scenario_id": scenario_id,
                "family": SCENARIO_FAMILIES[family_index],
                "variant": "injected",
                "severity": max(
                    cast(float, path["severity"])
                    for path in truth_paths
                    if path["scenario_id"] == scenario_id
                ),
                "starting_ids_json": stable_json(sorted(set(start_ids))),
                "target_ids_json": stable_json(sorted(set(target_ids))),
                "removable_candidates_json": stable_json(removal_candidates),
                "protected_edge_ids_json": "[]",
                "path_ids_json": stable_json(path_ids),
                "clean_counterpart_id": f"clean:{state.profile}:{state.scale}:{state.seed}",
                "is_hard_negative": False,
                "blocked_reason": None,
            }
        )
        negative_id, negative_metadata = _add_hard_negative(
            state,
            family_index,
            edges,
            conditions,
            pools,
            target_ids[0],
        )
        metadata = json.loads(negative_metadata)
        truth_scenarios.append(
            {
                "scenario_id": negative_id,
                "family": SCENARIO_FAMILIES[family_index],
                "variant": "hard_negative",
                "severity": 0.0,
                "starting_ids_json": stable_json([metadata["start_id"]]),
                "target_ids_json": stable_json([target_ids[0]]),
                "removable_candidates_json": "[]",
                "protected_edge_ids_json": "[]",
                "path_ids_json": "[]",
                "clean_counterpart_id": f"clean:{state.profile}:{state.scale}:{state.seed}",
                "is_hard_negative": True,
                "blocked_reason": metadata["blocked_reason"],
            }
        )
    return RiskInjectionResult(
        edges=edges,
        conditions=conditions,
        truth_paths=truth_paths,
        truth_scenarios=truth_scenarios,
        intended_removals=tuple(sorted(set(intended_removals))),
    )
