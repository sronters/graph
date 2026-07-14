"""Convert truth-hidden Polars tables into validated domain models."""

import json
from dataclasses import dataclass

from graphtrust.data.io import DatasetBundle
from graphtrust.schemas.conditions import Condition, ConditionExpression
from graphtrust.schemas.edges import GraphEdge
from graphtrust.schemas.nodes import GraphNode


@dataclass(frozen=True, slots=True)
class CanonicalRecords:
    """Validated inference records; benchmark truth remains outside this object."""

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    conditions: tuple[Condition, ...]
    critical_asset_ids: tuple[str, ...]


def bundle_to_records(
    bundle: DatasetBundle,
    *,
    criticality_threshold: float = 0.70,
) -> CanonicalRecords:
    """Validate canonical rows and preserve the truth-separation boundary."""
    if not 0 <= criticality_threshold <= 1:
        raise ValueError("criticality_threshold must be in [0, 1]")
    nodes = tuple(
        GraphNode.model_validate(row) for row in bundle.nodes.sort("node_id").iter_rows(named=True)
    )
    edges = tuple(
        GraphEdge.model_validate(row) for row in bundle.edges.sort("edge_id").iter_rows(named=True)
    )
    conditions = tuple(
        Condition(
            condition_id=str(row["condition_id"]),
            expression=ConditionExpression.model_validate(json.loads(str(row["expression_json"]))),
            source_text=(None if row["source_text"] is None else str(row["source_text"])),
        )
        for row in bundle.conditions.sort("condition_id").iter_rows(named=True)
    )
    critical_asset_ids = tuple(
        str(value)
        for value in bundle.assets.filter(
            bundle.assets["is_critical"] & (bundle.assets["criticality"] >= criticality_threshold)
        )
        .sort("node_id")
        .get_column("node_id")
        .to_list()
    )
    return CanonicalRecords(
        nodes=nodes,
        edges=edges,
        conditions=conditions,
        critical_asset_ids=critical_asset_ids,
    )
