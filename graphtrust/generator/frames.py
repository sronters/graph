"""Typed Polars frame construction for generator records."""

from collections.abc import Mapping, Sequence

import polars as pl

SchemaValue = type[pl.DataType] | pl.DataType

NODE_SCHEMA: dict[str, SchemaValue] = {
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
}
EDGE_SCHEMA: dict[str, SchemaValue] = {
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
}
CONDITION_SCHEMA: dict[str, SchemaValue] = {
    "condition_id": pl.String,
    "expression_json": pl.String,
    "source_text": pl.String,
}
ACTIVITY_SCHEMA: dict[str, SchemaValue] = {
    "node_id": pl.String,
    "window_start": pl.Datetime(time_zone="UTC"),
    "window_end": pl.Datetime(time_zone="UTC"),
    "event_count": pl.Int64,
    "last_activity_at": pl.Datetime(time_zone="UTC"),
}
ASSET_SCHEMA: dict[str, SchemaValue] = {
    "node_id": pl.String,
    "is_critical": pl.Boolean,
    "criticality": pl.Float64,
    "asset_class": pl.String,
}
TRUTH_PATH_SCHEMA: dict[str, SchemaValue] = {
    "path_id": pl.String,
    "scenario_id": pl.String,
    "source_id": pl.String,
    "target_id": pl.String,
    "edge_ids_json": pl.String,
    "severity": pl.Float64,
    "expected_detector_scope": pl.String,
    "semantic_signature_json": pl.String,
}
TRUTH_SCENARIO_SCHEMA: dict[str, SchemaValue] = {
    "scenario_id": pl.String,
    "family": pl.String,
    "variant": pl.String,
    "severity": pl.Float64,
    "starting_ids_json": pl.String,
    "target_ids_json": pl.String,
    "removable_candidates_json": pl.String,
    "protected_edge_ids_json": pl.String,
    "path_ids_json": pl.String,
    "clean_counterpart_id": pl.String,
    "is_hard_negative": pl.Boolean,
    "blocked_reason": pl.String,
}
REQUIREMENT_SCHEMA: dict[str, SchemaValue] = {
    "requirement_id": pl.String,
    "source_set_json": pl.String,
    "target_set_json": pl.String,
    "required_capability": pl.String,
    "minimum_remaining_paths": pl.Int64,
    "maximum_path_length": pl.Int64,
    "priority": pl.Int64,
    "protected_edge_ids_json": pl.String,
}


def records_frame(
    records: Sequence[Mapping[str, object]], schema: dict[str, SchemaValue]
) -> pl.DataFrame:
    """Construct typed frames even when record sequences are empty."""
    normalized = [{key: record.get(key) for key in schema} for record in records]
    return pl.DataFrame(normalized, schema=schema, orient="row")
