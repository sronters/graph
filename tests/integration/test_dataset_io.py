"""Canonical dataset persistence and validation tests."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from graphtrust.cli import app
from graphtrust.data.io import DatasetBundle, read_dataset, write_dataset
from graphtrust.data.validation import validate_bundle
from graphtrust.schemas.manifests import DatasetManifest, DatasetScale, DatasetVariant


def frame(rows: list[dict[str, object]], schema: dict[str, pl.DataType]) -> pl.DataFrame:
    """Create typed frames, including typed empty fixtures."""
    return pl.DataFrame(rows, schema=schema, orient="row")


def small_bundle() -> DatasetBundle:
    nodes = frame(
        [
            {
                "node_id": "human:1",
                "node_type": "HUMAN_IDENTITY",
                "display_name": "Synthetic Engineer 1",
                "provider": "INTERNAL",
                "tenant_id": "tenant:1",
                "environment": "CORPORATE",
                "department": "Engineering",
                "owner_node_id": None,
                "criticality": 0.1,
                "privilege_label": "LOW",
                "identity_status": "ACTIVE",
                "authentication_strength": 0.8,
                "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                "last_used_at": datetime(2026, 6, 1, tzinfo=UTC),
                "tags_json": "{}",
                "generator_seed": 104729,
            },
            {
                "node_id": "database:critical",
                "node_type": "DATABASE",
                "display_name": "Synthetic Customer Database",
                "provider": "AWS_LIKE",
                "tenant_id": "tenant:1",
                "environment": "PROD",
                "department": "Data",
                "owner_node_id": "human:1",
                "criticality": 0.95,
                "privilege_label": "NONE",
                "identity_status": "NOT_APPLICABLE",
                "authentication_strength": 1.0,
                "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                "last_used_at": None,
                "tags_json": "{}",
                "generator_seed": 104729,
            },
        ],
        {
            "node_id": pl.String,
            "node_type": pl.String,
            "display_name": pl.String,
            "provider": pl.String,
            "tenant_id": pl.String,
            "environment": pl.String,
            "department": pl.String,
            "owner_node_id": pl.String,
            "criticality": pl.Float64,
            "privilege_label": pl.String,
            "identity_status": pl.String,
            "authentication_strength": pl.Float64,
            "created_at": pl.Datetime(time_zone="UTC"),
            "last_used_at": pl.Datetime(time_zone="UTC"),
            "tags_json": pl.String,
            "generator_seed": pl.Int64,
        },
    )
    edges = frame(
        [
            {
                "edge_id": "edge:1",
                "source_id": "human:1",
                "target_id": "database:critical",
                "edge_type": "READS",
                "provider": "AWS_LIKE",
                "effect": "ALLOW",
                "scope": "database:critical",
                "condition_id": None,
                "direct": True,
                "derived": False,
                "derivation_rule": None,
                "confidence": 1.0,
                "relative_exploitability": 0.95,
                "business_removal_cost": 2.0,
                "removable": True,
                "protected": False,
                "active": True,
                "valid_from": None,
                "valid_until": None,
                "source_artifact": "fixture",
            }
        ],
        {
            "edge_id": pl.String,
            "source_id": pl.String,
            "target_id": pl.String,
            "edge_type": pl.String,
            "provider": pl.String,
            "effect": pl.String,
            "scope": pl.String,
            "condition_id": pl.String,
            "direct": pl.Boolean,
            "derived": pl.Boolean,
            "derivation_rule": pl.String,
            "confidence": pl.Float64,
            "relative_exploitability": pl.Float64,
            "business_removal_cost": pl.Float64,
            "removable": pl.Boolean,
            "protected": pl.Boolean,
            "active": pl.Boolean,
            "valid_from": pl.Datetime(time_zone="UTC"),
            "valid_until": pl.Datetime(time_zone="UTC"),
            "source_artifact": pl.String,
        },
    )
    manifest = DatasetManifest(
        dataset_id="seib-2026:saas_scaleup:small:104729:injected_low",
        profile="saas_scaleup",
        scale=DatasetScale.SMALL,
        variant=DatasetVariant.INJECTED_LOW,
        generator_seed=104729,
        generated_at=datetime(2026, 7, 14, tzinfo=UTC),
        git_commit="test-commit",
        config_sha256="a" * 64,
        package_lock_sha256="b" * 64,
        files={},
        realized_counts={"nodes": 2, "edges": 1, "scenarios": 1},
    )
    return DatasetBundle(
        nodes=nodes,
        edges=edges,
        conditions=frame(
            [],
            {"condition_id": pl.String, "expression_json": pl.String, "source_text": pl.String},
        ),
        activity=frame(
            [
                {
                    "node_id": "human:1",
                    "window_start": datetime(2026, 1, 1, tzinfo=UTC),
                    "window_end": datetime(2026, 6, 30, tzinfo=UTC),
                    "event_count": 20,
                    "last_activity_at": datetime(2026, 6, 1, tzinfo=UTC),
                }
            ],
            {
                "node_id": pl.String,
                "window_start": pl.Datetime(time_zone="UTC"),
                "window_end": pl.Datetime(time_zone="UTC"),
                "event_count": pl.Int64,
                "last_activity_at": pl.Datetime(time_zone="UTC"),
            },
        ),
        assets=frame(
            [
                {
                    "node_id": "database:critical",
                    "is_critical": True,
                    "criticality": 0.95,
                    "asset_class": "customer_data",
                }
            ],
            {
                "node_id": pl.String,
                "is_critical": pl.Boolean,
                "criticality": pl.Float64,
                "asset_class": pl.String,
            },
        ),
        truth_paths=frame(
            [
                {
                    "path_id": "path:1",
                    "scenario_id": "scenario:1",
                    "source_id": "human:1",
                    "target_id": "database:critical",
                    "edge_ids_json": '["edge:1"]',
                    "severity": 0.7,
                    "expected_detector_scope": "direct",
                }
            ],
            {
                "path_id": pl.String,
                "scenario_id": pl.String,
                "source_id": pl.String,
                "target_id": pl.String,
                "edge_ids_json": pl.String,
                "severity": pl.Float64,
                "expected_detector_scope": pl.String,
            },
        ),
        truth_scenarios=frame(
            [
                {
                    "scenario_id": "scenario:1",
                    "family": "fixture",
                    "variant": "injected_low",
                    "severity": 0.7,
                    "starting_ids_json": '["human:1"]',
                    "target_ids_json": '["database:critical"]',
                    "removable_candidates_json": '["edge:1"]',
                    "protected_edge_ids_json": "[]",
                }
            ],
            {
                "scenario_id": pl.String,
                "family": pl.String,
                "variant": pl.String,
                "severity": pl.Float64,
                "starting_ids_json": pl.String,
                "target_ids_json": pl.String,
                "removable_candidates_json": pl.String,
                "protected_edge_ids_json": pl.String,
            },
        ),
        protected_requirements=frame(
            [
                {
                    "requirement_id": "requirement:1",
                    "source_set_json": '["human:1"]',
                    "target_set_json": '["database:critical"]',
                    "required_capability": "READS",
                    "minimum_remaining_paths": 1,
                    "maximum_path_length": 2,
                    "priority": 10,
                }
            ],
            {
                "requirement_id": pl.String,
                "source_set_json": pl.String,
                "target_set_json": pl.String,
                "required_capability": pl.String,
                "minimum_remaining_paths": pl.Int64,
                "maximum_path_length": pl.Int64,
                "priority": pl.Int64,
            },
        ),
        manifest=manifest,
        quality_report={"valid": True, "orphan_count": 0},
    )


def test_dataset_round_trip_is_verified_and_deterministic(tmp_path: Path) -> None:
    bundle = small_bundle()
    first = write_dataset(bundle, tmp_path / "first")
    second = write_dataset(bundle, tmp_path / "second")
    loaded = read_dataset(tmp_path / "first")

    assert first.tree_checksum == second.tree_checksum == loaded.tree_checksum
    assert loaded.nodes.height == 2
    assert loaded.manifest.files["nodes.parquet"]
    assert "Truth separation" in (loaded.dataset_card or "")


def test_checksum_corruption_is_detected(tmp_path: Path) -> None:
    write_dataset(small_bundle(), tmp_path / "dataset")
    with (tmp_path / "dataset" / "dataset_card.md").open("a", encoding="utf-8") as stream:
        stream.write("tampered")
    with pytest.raises(ValueError, match="checksum verification failed"):
        read_dataset(tmp_path / "dataset")


def test_truth_columns_are_rejected_from_inference_frames() -> None:
    bundle = small_bundle()
    leaked = bundle.nodes.with_columns(pl.lit("scenario:1").alias("ground_truth_labels_json"))
    report = validate_bundle(replace(bundle, nodes=leaked))
    assert not report.valid
    assert any("truth columns leaked" in error for error in report.errors)


def test_unknown_edge_endpoint_is_rejected() -> None:
    bundle = small_bundle()
    invalid_edges = bundle.edges.with_columns(pl.lit("missing:node").alias("target_id"))
    report = validate_bundle(replace(bundle, edges=invalid_edges))
    assert not report.valid
    assert any("unknown edge targets" in error for error in report.errors)


def test_validate_data_cli_reports_verified_dataset(tmp_path: Path) -> None:
    destination = tmp_path / "dataset"
    written = write_dataset(small_bundle(), destination)
    result = CliRunner().invoke(
        app,
        ["validate-data", "--dataset", str(destination), "--json"],
    )
    assert result.exit_code == 0, result.output
    assert '"valid": true' in result.output
    assert written.tree_checksum in result.output
