"""Referential and truth-separation validation for canonical datasets."""

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from graphtrust.data.io import DatasetBundle

REQUIRED_COLUMNS: dict[str, frozenset[str]] = {
    "nodes": frozenset(
        {
            "node_id",
            "node_type",
            "display_name",
            "provider",
            "tenant_id",
            "environment",
            "department",
            "owner_node_id",
            "criticality",
            "privilege_label",
            "identity_status",
            "authentication_strength",
            "created_at",
            "last_used_at",
            "tags_json",
            "generator_seed",
        }
    ),
    "edges": frozenset(
        {
            "edge_id",
            "source_id",
            "target_id",
            "edge_type",
            "provider",
            "effect",
            "scope",
            "condition_id",
            "direct",
            "derived",
            "derivation_rule",
            "confidence",
            "relative_exploitability",
            "business_removal_cost",
            "removable",
            "protected",
            "active",
            "valid_from",
            "valid_until",
            "source_artifact",
        }
    ),
    "conditions": frozenset({"condition_id", "expression_json", "source_text"}),
    "activity": frozenset(
        {"node_id", "window_start", "window_end", "event_count", "last_activity_at"}
    ),
    "assets": frozenset({"node_id", "is_critical", "criticality", "asset_class"}),
    "truth_paths": frozenset(
        {
            "path_id",
            "scenario_id",
            "source_id",
            "target_id",
            "edge_ids_json",
            "severity",
            "expected_detector_scope",
        }
    ),
    "truth_scenarios": frozenset(
        {
            "scenario_id",
            "family",
            "variant",
            "severity",
            "starting_ids_json",
            "target_ids_json",
            "removable_candidates_json",
            "protected_edge_ids_json",
        }
    ),
    "protected_requirements": frozenset(
        {
            "requirement_id",
            "source_set_json",
            "target_set_json",
            "required_capability",
            "minimum_remaining_paths",
            "maximum_path_length",
            "priority",
        }
    ),
}

TRUTH_COLUMNS = frozenset({"ground_truth_labels_json", "ground_truth_scenario_id"})


@dataclass(frozen=True, slots=True)
class DatasetValidationReport:
    """Machine-readable validation result."""

    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    counts: dict[str, int]


def _duplicate_values(frame: pl.DataFrame, column: str) -> list[str]:
    if column not in frame.columns or frame.is_empty():
        return []
    duplicates = frame.group_by(column).len().filter(pl.col("len") > 1).get_column(column)
    return [str(value) for value in duplicates.to_list()]


def _set(frame: pl.DataFrame, column: str) -> set[str]:
    if column not in frame.columns:
        return set()
    return {str(value) for value in frame.get_column(column).drop_nulls().to_list()}


def validate_bundle(bundle: "DatasetBundle") -> DatasetValidationReport:
    """Validate schema presence, IDs, references, and inference/truth separation."""
    frames: dict[str, pl.DataFrame] = {
        "nodes": bundle.nodes,
        "edges": bundle.edges,
        "conditions": bundle.conditions,
        "activity": bundle.activity,
        "assets": bundle.assets,
        "truth_paths": bundle.truth_paths,
        "truth_scenarios": bundle.truth_scenarios,
        "protected_requirements": bundle.protected_requirements,
    }
    errors: list[str] = []
    warnings: list[str] = []
    for name, frame in frames.items():
        missing = REQUIRED_COLUMNS[name] - frozenset(frame.columns)
        if missing:
            errors.append(f"{name} missing columns: {', '.join(sorted(missing))}")

    leaked = TRUTH_COLUMNS.intersection(bundle.nodes.columns) | TRUTH_COLUMNS.intersection(
        bundle.edges.columns
    )
    if leaked:
        errors.append("truth columns leaked into inference tables: " + ", ".join(sorted(leaked)))

    for name, column in (
        ("nodes", "node_id"),
        ("edges", "edge_id"),
        ("conditions", "condition_id"),
        ("truth_paths", "path_id"),
        ("truth_scenarios", "scenario_id"),
        ("protected_requirements", "requirement_id"),
    ):
        duplicates = _duplicate_values(frames[name], column)
        if duplicates:
            errors.append(f"{name}.{column} contains duplicates: {duplicates[:5]}")

    node_ids = _set(bundle.nodes, "node_id")
    edge_ids = _set(bundle.edges, "edge_id")
    condition_ids = _set(bundle.conditions, "condition_id")
    scenario_ids = _set(bundle.truth_scenarios, "scenario_id")

    missing_sources = _set(bundle.edges, "source_id") - node_ids
    missing_targets = _set(bundle.edges, "target_id") - node_ids
    missing_owners = _set(bundle.nodes, "owner_node_id") - node_ids
    missing_conditions = _set(bundle.edges, "condition_id") - condition_ids
    missing_activity_nodes = _set(bundle.activity, "node_id") - node_ids
    missing_assets = _set(bundle.assets, "node_id") - node_ids
    missing_truth_sources = _set(bundle.truth_paths, "source_id") - node_ids
    missing_truth_targets = _set(bundle.truth_paths, "target_id") - node_ids
    missing_truth_scenarios = _set(bundle.truth_paths, "scenario_id") - scenario_ids

    if "edge_ids_json" in bundle.truth_paths.columns:
        for path_id, encoded_edges in bundle.truth_paths.select(
            "path_id", "edge_ids_json"
        ).iter_rows():
            try:
                path_edges = json.loads(encoded_edges)
            except (TypeError, json.JSONDecodeError):
                errors.append(f"truth path {path_id} has invalid edge_ids_json")
                continue
            if not isinstance(path_edges, list) or not path_edges:
                errors.append(f"truth path {path_id} must contain at least one edge")
                continue
            unknown_path_edges = {str(edge_id) for edge_id in path_edges} - edge_ids
            if unknown_path_edges:
                errors.append(
                    f"truth path {path_id} references unknown edges: "
                    f"{sorted(unknown_path_edges)[:5]}"
                )

    for label, values in (
        ("edge sources", missing_sources),
        ("edge targets", missing_targets),
        ("node owners", missing_owners),
        ("edge conditions", missing_conditions),
        ("activity nodes", missing_activity_nodes),
        ("asset nodes", missing_assets),
        ("truth path sources", missing_truth_sources),
        ("truth path targets", missing_truth_targets),
        ("truth path scenarios", missing_truth_scenarios),
    ):
        if values:
            errors.append(f"unknown {label}: {sorted(values)[:5]}")

    if REQUIRED_COLUMNS["edges"].issubset(bundle.edges.columns):
        invalid_costs = bundle.edges.filter(pl.col("business_removal_cost") <= 0).height
        invalid_risk = bundle.edges.filter(
            (pl.col("relative_exploitability") <= 0) | (pl.col("relative_exploitability") > 1)
        ).height
        protected_removable = bundle.edges.filter(pl.col("protected") & pl.col("removable")).height
        derived_without_rule = bundle.edges.filter(
            pl.col("derived") & pl.col("derivation_rule").is_null()
        ).height
        if invalid_costs:
            errors.append(f"edges with non-positive removal cost: {invalid_costs}")
        if invalid_risk:
            errors.append(f"edges with relative exploitability outside (0,1]: {invalid_risk}")
        if protected_removable:
            errors.append(f"protected edges marked removable: {protected_removable}")
        if derived_without_rule:
            errors.append(f"derived edges without named rule: {derived_without_rule}")

    if not bundle.truth_scenarios.is_empty() and bundle.truth_paths.is_empty():
        warnings.append("truth scenarios exist without enumerated truth paths")
    if bundle.nodes.is_empty():
        warnings.append("dataset contains no nodes")
    if bundle.edges.is_empty():
        warnings.append("dataset contains no edges")

    counts = {name: frame.height for name, frame in frames.items()}
    return DatasetValidationReport(
        valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
        counts=counts,
    )
