"""Generate deterministic departments, regions, and correlated teams."""

from dataclasses import dataclass

from graphtrust.generator.models import GenerationState


@dataclass(frozen=True, slots=True)
class Team:
    team_id: str
    department: str
    region: str
    product_area: str


@dataclass(frozen=True, slots=True)
class Organization:
    departments: tuple[str, ...]
    regions: tuple[str, ...]
    teams: tuple[Team, ...]


def generate_organization(state: GenerationState) -> Organization:
    """Create hierarchy before any identities or systems exist."""
    departments = tuple(str(item) for item in state.config["departments"])
    regions = tuple(str(item) for item in state.config["regions"])
    target_team_size = 9 if state.profile == "saas_scaleup" else 12
    team_count = max(len(departments), round(state.spec.humans / target_team_size))
    product_areas = (
        "Identity",
        "Payments",
        "Customer Data",
        "Analytics",
        "Core Platform",
        "Operations",
        "Governance",
        "Developer Experience",
    )
    teams = tuple(
        Team(
            team_id=f"team:{state.profile}:{index:05d}",
            department=departments[index % len(departments)],
            region=regions[(index // len(departments)) % len(regions)],
            product_area=product_areas[index % len(product_areas)],
        )
        for index in range(team_count)
    )
    state.team_members.update({team.team_id: [] for team in teams})
    state.department_members.update({department: [] for department in departments})
    return Organization(departments=departments, regions=regions, teams=teams)
