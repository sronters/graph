"""Generate owned applications, cloud hierarchy, and critical resources."""

from dataclasses import dataclass
from datetime import timedelta

from graphtrust.generator.models import GenerationState, stable_json
from graphtrust.generator.organization import Organization

RESOURCE_TYPES = (
    "APPLICATION",
    "REPOSITORY",
    "PIPELINE",
    "SECRET",
    "DATASET",
    "DATABASE",
    "STORAGE_BUCKET",
    "COMPUTE_RESOURCE",
    "CLOUD_ACCOUNT",
    "CLOUD_PROJECT",
    "CLOUD_FOLDER",
    "SAAS_TENANT",
    "NETWORK_ZONE",
    "POLICY",
    "PERMISSION_SET",
)


@dataclass(frozen=True, slots=True)
class ResourceCatalog:
    by_type: dict[str, tuple[str, ...]]
    critical_assets: tuple[str, ...]
    noncritical_resources: tuple[str, ...]


def generate_resources(
    state: GenerationState,
    organization: Organization,
) -> ResourceCatalog:
    """Create resources with team ownership and sparse production criticality."""
    by_type: dict[str, list[str]] = {resource_type: [] for resource_type in RESOURCE_TYPES}
    critical_assets: list[str] = []
    noncritical: list[str] = []
    active_by_department = {
        department: [
            node_id
            for node_id in members
            if state.node_by_id[node_id]["identity_status"] == "ACTIVE"
        ]
        for department, members in state.department_members.items()
    }
    for index in range(state.spec.resources):
        resource_type = RESOURCE_TYPES[index % len(RESOURCE_TYPES)]
        team = organization.teams[(index * 5) % len(organization.teams)]
        department = team.department
        environment = "PROD" if index % 4 == 0 else "STAGING" if index % 4 == 1 else "DEV"
        critical = (
            environment == "PROD"
            and resource_type
            in {
                "SECRET",
                "DATASET",
                "DATABASE",
                "STORAGE_BUCKET",
                "POLICY",
            }
            and index % 9 == 0
        )
        criticality = (
            0.75 + 0.24 * float(state.rng.random())
            if critical
            else 0.05 + 0.58 * float(state.rng.beta(2, 5))
        )
        prefix = resource_type.lower()
        resource_id = f"{prefix}:{state.profile}:{state.seed}:{index:07d}"
        provider = ("AWS_LIKE", "AZURE_LIKE", "GCP_LIKE", "SAAS")[index % 4]
        owner_pool = active_by_department[department]
        owner_id = owner_pool[index % len(owner_pool)]
        state.add_node(
            {
                "node_id": resource_id,
                "node_type": resource_type,
                "display_name": f"Synthetic {resource_type.replace('_', ' ').title()} {index + 1}",
                "provider": provider,
                "tenant_id": f"tenant:{state.profile}:{provider.lower()}",
                "environment": environment,
                "department": department,
                "owner_node_id": owner_id,
                "criticality": round(criticality, 6),
                "privilege_label": "NONE",
                "identity_status": "NOT_APPLICABLE",
                "authentication_strength": 1.0,
                "created_at": state.generated_at - timedelta(days=100 + index % 2_000),
                "last_used_at": None,
                "tags_json": stable_json(
                    {
                        "asset_class": ("customer_data" if critical else "business_system"),
                        "region": team.region,
                        "team_id": team.team_id,
                    }
                ),
                "generator_seed": state.seed,
            }
        )
        by_type[resource_type].append(resource_id)
        state.assets.append(
            {
                "node_id": resource_id,
                "is_critical": critical,
                "criticality": round(criticality, 6),
                "asset_class": "crown_jewel" if critical else "standard",
            }
        )
        (critical_assets if critical else noncritical).append(resource_id)
    if not critical_assets:
        raise ValueError("Resource generation produced no critical assets")
    return ResourceCatalog(
        by_type={name: tuple(values) for name, values in by_type.items()},
        critical_assets=tuple(critical_assets),
        noncritical_resources=tuple(noncritical),
    )
