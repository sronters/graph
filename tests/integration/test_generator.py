"""SEIB-2026 coherence, pairing, and reproducibility tests."""

import json
from collections import Counter
from pathlib import Path
from typing import cast

import pytest

from graphtrust.data import read_dataset, validate_bundle
from graphtrust.generator.counterfactuals import apply_truth_remediation
from graphtrust.generator.frames import EDGE_SCHEMA, records_frame
from graphtrust.generator.models import SCALE_SPECS, ProfileName
from graphtrust.generator.risk_injection import SCENARIO_FAMILIES, inject_risk_scenarios
from graphtrust.generator.runner import build_clean_state, generate_dataset_suite
from graphtrust.remediation.business_constraints import verify_business_requirements
from graphtrust.remediation.factory import build_remediation_problem
from graphtrust.settings import load_project_config


def test_scale_targets_stay_inside_preregistered_ranges() -> None:
    small = SCALE_SPECS["small"]
    medium = SCALE_SPECS["medium"]
    large = SCALE_SPECS["large"]
    assert 180 <= small.humans <= 250
    assert 350 <= small.non_humans <= 600
    assert 250 <= small.groups + small.roles <= 450
    assert 700 <= small.resources <= 1_200
    assert 8_000 <= small.raw_edges <= 20_000
    assert 1_800 <= medium.humans <= 2_500
    assert 5_000 <= medium.non_humans <= 8_000
    assert 2_500 <= medium.groups + medium.roles <= 4_500
    assert 12_000 <= medium.resources <= 20_000
    assert 150_000 <= medium.raw_edges <= 400_000
    assert 12_000 <= large.humans <= 18_000
    assert 45_000 <= large.non_humans <= 70_000
    assert 20_000 <= large.groups + large.roles <= 35_000
    assert 100_000 <= large.resources <= 180_000
    assert 1_500_000 <= large.raw_edges <= 4_000_000


@pytest.mark.parametrize(
    "profile",
    ["saas_scaleup", "regulated_finance", "global_hybrid"],
)
def test_all_profiles_build_coherent_small_clean_graph(profile: str) -> None:
    state, resources, _ = build_clean_state(cast(ProfileName, profile), "small", 104729)
    spec = SCALE_SPECS["small"]
    assert len(state.nodes_by_type["HUMAN_IDENTITY"]) == spec.humans
    assert (
        sum(
            len(state.nodes_by_type[name])
            for name in ("SERVICE_ACCOUNT", "WORKLOAD_IDENTITY", "EXTERNAL_IDENTITY")
        )
        == spec.non_humans
    )
    assert len(state.nodes_by_type["GROUP"]) + len(state.nodes_by_type["ROLE"]) == (
        spec.groups + spec.roles
    )
    assert len(state.assets) == spec.resources
    assert len(state.edges) == spec.raw_edges
    assert resources.critical_assets
    assert len(state.protected_requirements) == len(resources.critical_assets)


def test_all_scenario_families_have_truth_paths_and_hard_negatives() -> None:
    state, resources, _ = build_clean_state("saas_scaleup", "small", 104729)
    injected = inject_risk_scenarios(state, resources, family_count=12)
    positive = [
        scenario for scenario in injected.truth_scenarios if not scenario["is_hard_negative"]
    ]
    negatives = [scenario for scenario in injected.truth_scenarios if scenario["is_hard_negative"]]
    assert {scenario["family"] for scenario in positive} == set(SCENARIO_FAMILIES)
    assert len(positive) == len(negatives) == 12
    assert len(injected.truth_paths) == 13
    expected_path_counts = json.loads(
        Path("tests/fixtures/scenario_families.json").read_text(encoding="utf-8")
    )
    scenario_family = {
        str(scenario["scenario_id"]): str(scenario["family"]) for scenario in positive
    }
    realized_path_counts = Counter(
        scenario_family[str(path["scenario_id"])] for path in injected.truth_paths
    )
    assert realized_path_counts == expected_path_counts
    assert {scenario["blocked_reason"] for scenario in negatives} == {
        "disabled_identity",
        "expired_assignment",
        "explicit_deny",
        "false_condition",
        "inactive_relationship",
    }
    edge_ids = {str(edge["edge_id"]) for edge in injected.edges}
    for path in injected.truth_paths:
        assert set(json.loads(str(path["edge_ids_json"]))) <= edge_ids

    remediated = apply_truth_remediation(injected)
    active_by_id = {str(edge["edge_id"]): bool(edge["active"]) for edge in remediated.edges}
    assert all(not active_by_id[edge_id] for edge_id in injected.intended_removals)


def test_generated_edges_do_not_leak_truth_columns() -> None:
    state, resources, _ = build_clean_state("saas_scaleup", "small", 104729)
    injected = inject_risk_scenarios(state, resources, family_count=12)
    edge_frame = records_frame(injected.edges, EDGE_SCHEMA)
    assert "ground_truth_scenario_id" not in edge_frame.columns
    assert all("ground_truth" not in column for column in edge_frame.columns)


def test_same_seed_and_config_produce_identical_dataset_tree(tmp_path: Path) -> None:
    first = generate_dataset_suite(
        profile="saas_scaleup",
        scale="small",
        seed=104729,
        variants=("clean",),
        output_root=tmp_path / "first",
    )[0]
    second = generate_dataset_suite(
        profile="saas_scaleup",
        scale="small",
        seed=104729,
        variants=("clean",),
        output_root=tmp_path / "second",
    )[0]
    assert first.tree_checksum == second.tree_checksum
    loaded = read_dataset(first.destination)
    report = validate_bundle(loaded)
    assert report.valid
    assert loaded.manifest.realized_counts["raw_edges"] == 12_000


def test_generated_protected_workflows_are_valid_before_remediation(tmp_path: Path) -> None:
    generated = generate_dataset_suite(
        profile="saas_scaleup",
        scale="small",
        seed=104729,
        variants=("injected_mixed",),
        output_root=tmp_path,
    )[0]
    problem = build_remediation_problem(
        generated.destination,
        load_project_config(Path("configs/default.yaml")),
    )
    verification = verify_business_requirements(problem, ())
    assert verification.valid
    assert all(
        result.remaining_paths >= result.required_paths for result in verification.requirements
    )
