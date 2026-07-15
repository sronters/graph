"""Generate human and non-human identities from organization structure."""

from datetime import timedelta

from graphtrust.generator.models import GenerationState, stable_json
from graphtrust.generator.organization import Organization


def _created_and_used(state: GenerationState, dormant: bool) -> tuple[object, object]:
    created_days = int(state.rng.integers(200, 2_500))
    created_at = state.generated_at - timedelta(days=created_days)
    last_used_days = int(state.rng.integers(95, 360) if dormant else state.rng.integers(0, 45))
    return created_at, state.generated_at - timedelta(days=last_used_days)


def generate_human_identities(state: GenerationState, organization: Organization) -> None:
    """Generate employees with exactly one team and correlated status/churn."""
    contractor_share = float(state.config["contractor_share"])
    job_families = ("Engineering", "Operations", "Analysis", "Management", "Specialist")
    for index in range(state.spec.humans):
        team = organization.teams[index % len(organization.teams)]
        is_contractor = bool(state.rng.random() < contractor_share)
        status_roll = float(state.rng.random())
        status = (
            "DISABLED"
            if index == 0 or status_roll < 0.018
            else "DORMANT"
            if index in {1, 2} or status_roll < 0.075
            else "ACTIVE"
        )
        created_at, last_used_at = _created_and_used(state, status == "DORMANT")
        node_id = f"human:{state.profile}:{state.seed}:{index:06d}"
        authentication = float(state.rng.beta(8, 2))
        state.add_node(
            {
                "node_id": node_id,
                "node_type": "HUMAN_IDENTITY",
                "display_name": f"Synthetic {team.department} Person {index + 1}",
                "provider": "INTERNAL",
                "tenant_id": f"tenant:{state.profile}:directory",
                "environment": "CORPORATE",
                "department": team.department,
                "owner_node_id": None,
                "criticality": round(float(state.rng.beta(1.5, 12)), 6),
                "privilege_label": "LOW" if index % 11 else "MEDIUM",
                "identity_status": status,
                "authentication_strength": round(authentication, 6),
                "created_at": created_at,
                "last_used_at": last_used_at,
                "tags_json": stable_json(
                    {
                        "employment_type": "CONTRACTOR" if is_contractor else "EMPLOYEE",
                        "job_family": job_families[index % len(job_families)],
                        "region": team.region,
                        "seniority": 1 + index % 6,
                        "team_id": team.team_id,
                    }
                ),
                "generator_seed": state.seed,
            }
        )
        state.team_members[team.team_id].append(node_id)
        state.department_members[team.department].append(node_id)


def generate_non_human_identities(state: GenerationState, organization: Organization) -> None:
    """Generate over-dispersed service/workload identities tied to teams."""
    for index in range(state.spec.non_humans):
        slot = index % 20
        node_type = (
            "SERVICE_ACCOUNT"
            if slot < 11
            else "WORKLOAD_IDENTITY"
            if slot < 19
            else "EXTERNAL_IDENTITY"
        )
        team = organization.teams[(index * 7) % len(organization.teams)]
        status_roll = float(state.rng.random())
        status = (
            "DISABLED" if status_roll < 0.015 else "DORMANT" if status_roll < 0.09 else "ACTIVE"
        )
        created_at, last_used_at = _created_and_used(state, status == "DORMANT")
        prefix = {
            "SERVICE_ACCOUNT": "service",
            "WORKLOAD_IDENTITY": "workload",
            "EXTERNAL_IDENTITY": "external",
        }[node_type]
        node_id = f"{prefix}:{state.profile}:{state.seed}:{index:07d}"
        state.add_node(
            {
                "node_id": node_id,
                "node_type": node_type,
                "display_name": f"Synthetic {prefix.title()} Identity {index + 1}",
                "provider": ("SAAS" if node_type == "EXTERNAL_IDENTITY" else "GENERIC"),
                "tenant_id": (
                    f"tenant:{state.profile}:partner"
                    if node_type == "EXTERNAL_IDENTITY"
                    else f"tenant:{state.profile}:cloud"
                ),
                "environment": "PROD" if index % 4 == 0 else "DEV",
                "department": team.department if node_type != "EXTERNAL_IDENTITY" else "SYSTEM",
                "owner_node_id": state.team_members[team.team_id][0],
                "criticality": round(float(state.rng.beta(2, 9)), 6),
                "privilege_label": "MEDIUM" if index % 23 == 0 else "LOW",
                "identity_status": status,
                "authentication_strength": round(float(state.rng.beta(7, 2.5)), 6),
                "created_at": created_at,
                "last_used_at": last_used_at,
                "tags_json": stable_json(
                    {
                        "application_slot": index % max(1, state.spec.resources // 10),
                        "region": team.region,
                        "team_id": team.team_id,
                    }
                ),
                "generator_seed": state.seed,
            }
        )
