"""Generate heavy-tailed groups, correlated membership, and bounded nesting."""

from dataclasses import dataclass
from datetime import timedelta

from graphtrust.generator.models import GenerationState, stable_json
from graphtrust.generator.organization import Organization


@dataclass(frozen=True, slots=True)
class GroupCatalog:
    team_groups: dict[str, str]
    department_groups: dict[str, str]
    access_groups: tuple[str, ...]
    legacy_groups: tuple[str, ...]


def generate_groups(state: GenerationState, organization: Organization) -> GroupCatalog:
    """Generate group objects before membership and nesting edges."""
    team_groups: dict[str, str] = {}
    department_groups: dict[str, str] = {}
    access_groups: list[str] = []
    legacy_groups: list[str] = []
    for index in range(state.spec.groups):
        if index < len(organization.teams):
            team = organization.teams[index]
            purpose = "TEAM"
            department = team.department
            group_id = f"group:{state.profile}:team:{index:05d}"
            team_groups[team.team_id] = group_id
        elif index < len(organization.teams) + len(organization.departments):
            department_index = index - len(organization.teams)
            department = organization.departments[department_index]
            purpose = "DEPARTMENT"
            group_id = f"group:{state.profile}:department:{department_index:03d}"
            department_groups[department] = group_id
        else:
            residual = index - len(organization.teams) - len(organization.departments)
            is_legacy = residual % 9 == 0
            purpose = "LEGACY" if is_legacy else "ACCESS"
            department = organization.departments[residual % len(organization.departments)]
            group_id = f"group:{state.profile}:{purpose.lower()}:{residual:06d}"
            (legacy_groups if is_legacy else access_groups).append(group_id)
        state.add_node(
            {
                "node_id": group_id,
                "node_type": "GROUP",
                "display_name": f"Synthetic {purpose.title()} Group {index + 1}",
                "provider": "INTERNAL",
                "tenant_id": f"tenant:{state.profile}:directory",
                "environment": "CORPORATE",
                "department": department,
                "owner_node_id": state.department_members[department][0],
                "criticality": round(float(state.rng.beta(1.5, 10)), 6),
                "privilege_label": "NONE",
                "identity_status": "NOT_APPLICABLE",
                "authentication_strength": 1.0,
                "created_at": state.generated_at - timedelta(days=500 + index % 1_800),
                "last_used_at": None,
                "tags_json": stable_json({"group_purpose": purpose}),
                "generator_seed": state.seed,
            }
        )

    if not access_groups:
        access_groups.extend(team_groups.values())
    if not legacy_groups:
        legacy_groups.append(access_groups[0])
    return GroupCatalog(
        team_groups=team_groups,
        department_groups=department_groups,
        access_groups=tuple(access_groups),
        legacy_groups=tuple(legacy_groups),
    )


def generate_memberships(
    state: GenerationState,
    organization: Organization,
    groups: GroupCatalog,
) -> None:
    """Attach identities through correlated, heavy-tailed membership rules."""
    for team in organization.teams:
        team_group = groups.team_groups[team.team_id]
        department_group = groups.department_groups[team.department]
        state.add_edge(
            team_group,
            department_group,
            "NESTED_IN",
            relative_exploitability=0.9,
            business_removal_cost=state.random_cost(protected=True),
            protected=True,
        )
        for member_index, human_id in enumerate(state.team_members[team.team_id]):
            human = state.node_by_id[human_id]
            protected = str(human["identity_status"]) == "ACTIVE"
            state.add_edge(
                human_id,
                team_group,
                "MEMBER_OF",
                relative_exploitability=0.9,
                business_removal_cost=state.random_cost(protected=protected),
                protected=protected,
            )
            extra_memberships = min(4, 1 + int(state.rng.pareto(2.5)))
            for offset in range(extra_memberships):
                access_group = groups.access_groups[
                    (member_index * 31 + offset * 17 + len(team.team_id))
                    % len(groups.access_groups)
                ]
                state.add_edge(
                    human_id,
                    access_group,
                    "MEMBER_OF",
                    business_removal_cost=state.random_cost(),
                    relative_exploitability=0.9,
                )

    non_human_ids = [
        *state.nodes_by_type.get("SERVICE_ACCOUNT", []),
        *state.nodes_by_type.get("WORKLOAD_IDENTITY", []),
        *state.nodes_by_type.get("EXTERNAL_IDENTITY", []),
    ]
    for index, identity_id in enumerate(non_human_ids):
        if index % 3 == 0:
            state.add_edge(
                identity_id,
                groups.access_groups[(index * 11) % len(groups.access_groups)],
                "MEMBER_OF",
                business_removal_cost=state.random_cost(),
                relative_exploitability=0.9,
            )

    nested_pool = (*groups.access_groups, *groups.legacy_groups)
    max_nesting = min(len(nested_pool) - 1, max(1, state.spec.groups // 10))
    for index in range(max_nesting):
        child = nested_pool[index]
        parent = nested_pool[index + 1]
        if child != parent:
            state.add_edge(
                child,
                parent,
                "NESTED_IN",
                business_removal_cost=state.random_cost(),
                relative_exploitability=0.9,
            )
