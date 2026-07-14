"""End-to-end paired SEIB-2026 dataset generation."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from graphtrust.data.io import DatasetBundle, write_dataset
from graphtrust.generator.activity import generate_activity
from graphtrust.generator.counterfactuals import apply_truth_remediation
from graphtrust.generator.frames import (
    ACTIVITY_SCHEMA,
    ASSET_SCHEMA,
    CONDITION_SCHEMA,
    EDGE_SCHEMA,
    NODE_SCHEMA,
    REQUIREMENT_SCHEMA,
    TRUTH_PATH_SCHEMA,
    TRUTH_SCENARIO_SCHEMA,
    records_frame,
)
from graphtrust.generator.groups import generate_groups, generate_memberships
from graphtrust.generator.identities import (
    generate_human_identities,
    generate_non_human_identities,
)
from graphtrust.generator.models import (
    GenerationState,
    ProfileName,
    ScaleName,
    config_and_lock_hash,
)
from graphtrust.generator.organization import generate_organization
from graphtrust.generator.policies import fill_to_scale_edge_target, generate_permissions
from graphtrust.generator.quality_report import build_quality_report
from graphtrust.generator.resources import ResourceCatalog, generate_resources
from graphtrust.generator.risk_injection import RiskInjectionResult, inject_risk_scenarios
from graphtrust.generator.roles import generate_roles
from graphtrust.generator.workloads import (
    ensure_production_execution_identities,
    generate_workload_relationships,
)
from graphtrust.schemas.manifests import DatasetManifest, DatasetScale, DatasetVariant
from graphtrust.settings import load_yaml

SUPPORTED_VARIANTS = ("clean", "injected_low", "injected_mixed", "remediated_truth")


@dataclass(frozen=True, slots=True)
class GeneratedDataset:
    variant: str
    destination: Path
    dataset_id: str
    tree_checksum: str
    node_count: int
    edge_count: int
    scenario_count: int


def current_git_commit() -> str:
    """Resolve the exact source revision recorded in manifests."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def build_clean_state(
    profile: ProfileName,
    scale: ScaleName,
    seed: int,
    *,
    config_root: Path = Path("configs"),
) -> tuple[GenerationState, ResourceCatalog, Path]:
    """Build the clean company exactly once before paired cloning."""
    config_path = config_root / "enterprises" / f"{profile}.yaml"
    config = load_yaml(config_path)
    state = GenerationState(profile=profile, scale=scale, seed=seed, config=config)
    organization = generate_organization(state)
    generate_human_identities(state, organization)
    generate_non_human_identities(state, organization)
    groups = generate_groups(state, organization)
    generate_memberships(state, organization, groups)
    roles = generate_roles(state, organization, groups)
    resources = generate_resources(state, organization)
    generate_workload_relationships(state, resources)
    missing_execution = ensure_production_execution_identities(state, resources)
    if missing_execution:
        raise ValueError(f"Production workloads lack execution identity: {missing_execution[:5]}")
    generate_permissions(state, roles, resources)
    generate_activity(state)
    fill_to_scale_edge_target(state, resources, roles)
    return state, resources, config_path


def _variant_records(
    state: GenerationState,
    resources: ResourceCatalog,
    variant: str,
) -> RiskInjectionResult:
    if variant == "clean":
        return RiskInjectionResult(
            edges=[dict(edge) for edge in state.edges],
            conditions=[dict(condition) for condition in state.conditions],
            truth_paths=[],
            truth_scenarios=[],
            intended_removals=(),
        )
    if variant == "injected_low":
        return inject_risk_scenarios(state, resources, family_count=4)
    injected = inject_risk_scenarios(state, resources, family_count=12)
    return apply_truth_remediation(injected) if variant == "remediated_truth" else injected


def _bundle(
    state: GenerationState,
    resources: ResourceCatalog,
    variant: str,
    records: RiskInjectionResult,
    *,
    git_commit: str,
    config_sha256: str,
    lock_sha256: str,
) -> DatasetBundle:
    dataset_id = f"seib-2026:{state.profile}:{state.scale}:{state.seed}:{variant}"
    humans = len(state.nodes_by_type["HUMAN_IDENTITY"])
    non_humans = sum(
        len(state.nodes_by_type[name])
        for name in ("SERVICE_ACCOUNT", "WORKLOAD_IDENTITY", "EXTERNAL_IDENTITY")
    )
    quality = build_quality_report(
        state,
        resources,
        variant=variant,
        edges=records.edges,
        truth_scenarios=records.truth_scenarios,
        clean_edge_count=len(state.edges),
        condition_count=len(records.conditions),
        intended_removals=records.intended_removals,
    )
    if not quality["valid"]:
        raise ValueError(f"Generated dataset failed coherence checks: {quality['errors']}")
    manifest = DatasetManifest(
        dataset_id=dataset_id,
        profile=state.profile,
        scale=DatasetScale(state.scale),
        variant=DatasetVariant(variant),
        generator_seed=state.seed,
        generated_at=state.generated_at,
        git_commit=git_commit,
        config_sha256=config_sha256,
        package_lock_sha256=lock_sha256,
        files={},
        realized_counts={
            "nodes": len(state.nodes),
            "human_identities": humans,
            "non_human_identities": non_humans,
            "groups_and_roles": len(state.nodes_by_type["GROUP"])
            + len(state.nodes_by_type["ROLE"]),
            "resources": state.spec.resources,
            "raw_edges": len(records.edges),
            "truth_scenarios": len(records.truth_scenarios),
            "truth_paths": len(records.truth_paths),
        },
    )
    return DatasetBundle(
        nodes=records_frame(state.nodes, NODE_SCHEMA),
        edges=records_frame(records.edges, EDGE_SCHEMA),
        conditions=records_frame(records.conditions, CONDITION_SCHEMA),
        activity=records_frame(state.activity, ACTIVITY_SCHEMA),
        assets=records_frame(state.assets, ASSET_SCHEMA),
        truth_paths=records_frame(records.truth_paths, TRUTH_PATH_SCHEMA),
        truth_scenarios=records_frame(records.truth_scenarios, TRUTH_SCENARIO_SCHEMA),
        protected_requirements=records_frame(state.protected_requirements, REQUIREMENT_SCHEMA),
        manifest=manifest,
        quality_report=quality,
    )


def generate_dataset_suite(
    *,
    profile: str,
    scale: str,
    seed: int,
    variants: tuple[str, ...] = SUPPORTED_VARIANTS,
    output_root: Path = Path("data/generated"),
    config_root: Path = Path("configs"),
) -> tuple[GeneratedDataset, ...]:
    """Generate requested paired variants and atomically persist each one."""
    if profile not in {"saas_scaleup", "regulated_finance", "global_hybrid"}:
        raise ValueError(f"Unsupported enterprise profile: {profile}")
    if scale not in {"small", "medium", "large"}:
        raise ValueError(f"Unsupported scale: {scale}")
    invalid_variants = set(variants) - set(SUPPORTED_VARIANTS)
    if invalid_variants:
        raise ValueError(f"Unsupported variants: {sorted(invalid_variants)}")
    if len(set(variants)) != len(variants):
        raise ValueError("Variants must be unique")

    resolved_profile = cast(ProfileName, profile)
    resolved_scale = cast(ScaleName, scale)
    state, resources, config_path = build_clean_state(
        resolved_profile,
        resolved_scale,
        seed,
        config_root=config_root,
    )
    config_sha256, lock_sha256 = config_and_lock_hash(config_path)
    git_commit = current_git_commit()
    results: list[GeneratedDataset] = []
    for variant in variants:
        records = _variant_records(state, resources, variant)
        bundle = _bundle(
            state,
            resources,
            variant,
            records,
            git_commit=git_commit,
            config_sha256=config_sha256,
            lock_sha256=lock_sha256,
        )
        destination = output_root / profile / scale / str(seed) / variant
        written = write_dataset(bundle, destination)
        if written.tree_checksum is None:
            raise RuntimeError("Dataset writer did not return a tree checksum")
        results.append(
            GeneratedDataset(
                variant=variant,
                destination=destination,
                dataset_id=written.manifest.dataset_id,
                tree_checksum=written.tree_checksum,
                node_count=written.nodes.height,
                edge_count=written.edges.height,
                scenario_count=written.truth_scenarios.height,
            )
        )
    return tuple(results)
