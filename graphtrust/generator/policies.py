"""Generate permissions, conditions, denials, and protected workflows."""

from typing import cast

from graphtrust.generator.models import GenerationState
from graphtrust.generator.resources import ResourceCatalog
from graphtrust.generator.roles import RoleCatalog


def _true_environment_condition(state: GenerationState, environment: str) -> str:
    return state.add_condition(
        {
            "operator": "LEAF",
            "operand": "ENVIRONMENT",
            "comparator": "EQ",
            "expected": environment,
            "children": [],
        },
        f"environment equals {environment}",
    )


def generate_permissions(
    state: GenerationState,
    roles: RoleCatalog,
    resources: ResourceCatalog,
) -> None:
    """Generate correlated noncritical access plus explicit protected crown-jewel routes."""
    noncritical = list(resources.noncritical_resources)
    conditional_share = float(state.config["conditional_access_share"])
    permission_types = ("READS", "WRITES", "GRANTS_PERMISSION", "ADMINISTERS")
    for role_index, role_id in enumerate(roles.role_ids):
        role = state.node_by_id[role_id]
        grants = 5 + role_index % 8
        for grant_index in range(grants):
            target = noncritical[(role_index * 37 + grant_index * 101) % len(noncritical)]
            condition_id = None
            effect = "ALLOW"
            if float(state.rng.random()) < conditional_share:
                condition_id = _true_environment_condition(state, str(role["environment"]))
                effect = "CONDITIONAL"
            state.add_edge(
                role_id,
                target,
                permission_types[(role_index + grant_index) % len(permission_types)],
                provider=str(state.node_by_id[target]["provider"]),
                effect=effect,
                condition_id=condition_id,
                relative_exploitability=0.95,
                business_removal_cost=state.random_cost(),
            )

    policies = list(resources.by_type["POLICY"])
    attachable = [*roles.role_ids, *state.nodes_by_type["SERVICE_ACCOUNT"]]
    for index, policy_id in enumerate(policies):
        principal = attachable[(index * 19) % len(attachable)]
        target = noncritical[(index * 43) % len(noncritical)]
        state.add_edge(principal, policy_id, "POLICY_ATTACHED_TO")
        state.add_edge(policy_id, target, "GRANTS_PERMISSION", relative_exploitability=0.9)
        if index % 13 == 0:
            state.add_edge(
                principal,
                target,
                "DENIES",
                effect="DENY",
                removable=False,
                relative_exploitability=0.1,
            )

    active_humans = [
        node_id
        for node_id in state.nodes_by_type["HUMAN_IDENTITY"]
        if state.node_by_id[node_id]["identity_status"] == "ACTIVE"
    ]
    privileged_roles = list(roles.admin_roles or roles.production_roles)
    protected_operator_count = max(
        1,
        int(state.spec.humans * float(state.config["direct_privilege_max_share"]) * 0.5),
    )
    protected_operators = active_humans[:protected_operator_count]
    for index, asset_id in enumerate(resources.critical_assets):
        role_id = privileged_roles[index % len(privileged_roles)]
        owner_id = protected_operators[index % len(protected_operators)]
        assignment_id = state.add_edge(
            owner_id,
            role_id,
            "ASSIGNED_ROLE",
            provider=str(state.node_by_id[role_id]["provider"]),
            relative_exploitability=0.92,
            business_removal_cost=20,
            protected=True,
        )
        access_id = state.add_edge(
            role_id,
            asset_id,
            "APPROVED_ACCESS",
            provider=str(state.node_by_id[asset_id]["provider"]),
            relative_exploitability=0.35,
            business_removal_cost=25,
            protected=True,
        )
        state.protected_requirements.append(
            {
                "requirement_id": f"requirement:{state.profile}:{state.seed}:{index:05d}",
                "source_set_json": f'["{owner_id}"]',
                "target_set_json": f'["{asset_id}"]',
                "required_capability": "APPROVED_ACCESS",
                "minimum_remaining_paths": 1,
                "maximum_path_length": 3,
                "priority": 100,
                "protected_edge_ids_json": f'["{assignment_id}","{access_id}"]',
            }
        )


def fill_to_scale_edge_target(
    state: GenerationState,
    resources: ResourceCatalog,
    roles: RoleCatalog,
) -> None:
    """Reach the declared scale using correlated parallel policy sources."""
    if len(state.edges) > state.spec.raw_edges:
        raise ValueError(
            f"Base graph already exceeds edge target: {len(state.edges)} > {state.spec.raw_edges}"
        )
    source_pools = (
        list(roles.role_ids),
        state.nodes_by_type["SERVICE_ACCOUNT"],
        state.nodes_by_type["WORKLOAD_IDENTITY"],
        state.nodes_by_type["HUMAN_IDENTITY"],
    )
    noncritical = list(resources.noncritical_resources)
    edge_types = ("READS", "WRITES", "CAN_MODIFY", "MANAGES")
    index = 0
    while len(state.edges) < state.spec.raw_edges:
        pool = source_pools[index % len(source_pools)]
        source_id = pool[(index * 53) % len(pool)]
        source = state.node_by_id[source_id]
        target_id = noncritical[(index * 97 + index // max(1, len(noncritical))) % len(noncritical)]
        target = state.node_by_id[target_id]
        if source_id == target_id:
            index += 1
            continue
        protected = False
        condition_id = None
        effect = "ALLOW"
        if index % 17 == 0:
            condition_id = _true_environment_condition(state, str(source["environment"]))
            effect = "CONDITIONAL"
        recent_use = 1.0 if source["identity_status"] == "ACTIVE" else 0.2
        removal_cost = (
            0.5
            + 2.0 * recent_use
            + 2.0 * cast(float, target["criticality"])
            + float(state.rng.lognormal(0, 0.3))
        )
        state.add_edge(
            source_id,
            target_id,
            edge_types[index % len(edge_types)],
            provider=str(target["provider"]),
            effect=effect,
            condition_id=condition_id,
            business_removal_cost=round(removal_cost, 6),
            protected=protected,
        )
        index += 1
