"""Generate job-function roles and correlated role assignments."""

from dataclasses import dataclass
from datetime import timedelta

from graphtrust.generator.groups import GroupCatalog
from graphtrust.generator.models import GenerationState, stable_json
from graphtrust.generator.organization import Organization


@dataclass(frozen=True, slots=True)
class RoleCatalog:
    role_ids: tuple[str, ...]
    production_roles: tuple[str, ...]
    admin_roles: tuple[str, ...]


def generate_roles(
    state: GenerationState,
    organization: Organization,
    groups: GroupCatalog,
) -> RoleCatalog:
    """Create environment-specific roles and group/direct assignments."""
    role_ids: list[str] = []
    production_roles: list[str] = []
    admin_roles: list[str] = []
    for index in range(state.spec.roles):
        environment = "PROD" if index % 7 == 0 else "STAGING" if index % 5 == 0 else "DEV"
        is_admin = index % 47 == 0
        department = organization.departments[index % len(organization.departments)]
        role_id = f"role:{state.profile}:{state.seed}:{index:06d}"
        role_ids.append(role_id)
        if environment == "PROD":
            production_roles.append(role_id)
        if is_admin:
            admin_roles.append(role_id)
        state.add_node(
            {
                "node_id": role_id,
                "node_type": "ROLE",
                "display_name": f"Synthetic {environment.title()} {department} Role {index + 1}",
                "provider": ("AWS_LIKE", "AZURE_LIKE", "GCP_LIKE")[index % 3],
                "tenant_id": f"tenant:{state.profile}:cloud",
                "environment": environment,
                "department": department,
                "owner_node_id": state.department_members[department][0],
                "criticality": 0.8 if is_admin else round(float(state.rng.beta(2, 7)), 6),
                "privilege_label": "ADMIN"
                if is_admin
                else "HIGH"
                if environment == "PROD"
                else "MEDIUM",
                "identity_status": "NOT_APPLICABLE",
                "authentication_strength": 1.0,
                "created_at": state.generated_at - timedelta(days=300 + index % 1_700),
                "last_used_at": None,
                "tags_json": stable_json(
                    {"job_function": department, "role_environment": environment}
                ),
                "generator_seed": state.seed,
            }
        )

    assignable_groups = (*groups.access_groups, *groups.department_groups.values())
    for index, group_id in enumerate(assignable_groups):
        role_id = role_ids[(index * 13) % len(role_ids)]
        protected = index < len(organization.departments)
        state.add_edge(
            group_id,
            role_id,
            "ASSIGNED_ROLE",
            provider=str(state.node_by_id[role_id]["provider"]),
            relative_exploitability=0.92,
            business_removal_cost=state.random_cost(protected=protected),
            protected=protected,
        )

    maximum_direct_share = float(state.config["direct_privilege_max_share"])
    direct_assignments = max(1, int(state.spec.humans * maximum_direct_share * 0.5))
    active_humans = [
        node_id
        for node_id in state.nodes_by_type["HUMAN_IDENTITY"]
        if state.node_by_id[node_id]["identity_status"] == "ACTIVE"
    ]
    for index in range(direct_assignments):
        human_id = active_humans[index % len(active_humans)]
        role_id = production_roles[index % len(production_roles)]
        state.add_edge(
            human_id,
            role_id,
            "ASSIGNED_ROLE",
            provider=str(state.node_by_id[role_id]["provider"]),
            relative_exploitability=0.92,
            business_removal_cost=state.random_cost(protected=True),
            protected=True,
        )
    return RoleCatalog(
        role_ids=tuple(role_ids),
        production_roles=tuple(production_roles),
        admin_roles=tuple(admin_roles),
    )
