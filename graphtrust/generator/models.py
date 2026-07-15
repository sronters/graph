"""Shared deterministic generation state and scale contracts."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.random import Generator

from graphtrust.data.checksums import sha256_file

ScaleName = Literal["small", "medium", "large"]
ProfileName = Literal["saas_scaleup", "regulated_finance", "global_hybrid"]


@dataclass(frozen=True, slots=True)
class ScaleSpec:
    """Realized benchmark targets chosen inside the preregistered ranges."""

    humans: int
    non_humans: int
    groups: int
    roles: int
    resources: int
    raw_edges: int


SCALE_SPECS: dict[ScaleName, ScaleSpec] = {
    "small": ScaleSpec(220, 450, 210, 140, 900, 12_000),
    "medium": ScaleSpec(2_100, 6_500, 1_800, 1_700, 15_000, 250_000),
    "large": ScaleSpec(15_000, 55_000, 14_000, 13_000, 130_000, 2_500_000),
}

BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def stable_json(value: object) -> str:
    """Encode JSON independently of dictionary insertion order."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def deterministic_timestamp(seed: int, offset: int = 0) -> datetime:
    """Generate manifest-safe timestamps without wall-clock nondeterminism."""
    return BASE_TIME + timedelta(seconds=(seed + offset) % (365 * 24 * 60 * 60))


@dataclass(slots=True)
class GenerationState:
    """Mutable state used only during one deterministic clean-graph build."""

    profile: ProfileName
    scale: ScaleName
    seed: int
    config: dict[str, Any]
    rng: Generator = field(init=False)
    nodes: list[dict[str, object]] = field(default_factory=list)
    edges: list[dict[str, object]] = field(default_factory=list)
    conditions: list[dict[str, object]] = field(default_factory=list)
    activity: list[dict[str, object]] = field(default_factory=list)
    assets: list[dict[str, object]] = field(default_factory=list)
    protected_requirements: list[dict[str, object]] = field(default_factory=list)
    node_ids: set[str] = field(default_factory=set)
    edge_ids: set[str] = field(default_factory=set)
    condition_ids: set[str] = field(default_factory=set)
    node_by_id: dict[str, dict[str, object]] = field(default_factory=dict)
    team_members: dict[str, list[str]] = field(default_factory=dict)
    department_members: dict[str, list[str]] = field(default_factory=dict)
    nodes_by_type: dict[str, list[str]] = field(default_factory=dict)
    edge_counter: int = 0

    def __post_init__(self) -> None:
        self.rng = np.random.default_rng(self.seed)

    @property
    def spec(self) -> ScaleSpec:
        return SCALE_SPECS[self.scale]

    @property
    def generated_at(self) -> datetime:
        return deterministic_timestamp(self.seed)

    def add_node(self, record: dict[str, object]) -> None:
        node_id = str(record["node_id"])
        if node_id in self.node_ids:
            raise ValueError(f"Duplicate node ID: {node_id}")
        self.node_ids.add(node_id)
        self.nodes.append(record)
        self.node_by_id[node_id] = record
        self.nodes_by_type.setdefault(str(record["node_type"]), []).append(node_id)

    def add_condition(self, expression: dict[str, object], source_text: str) -> str:
        condition_id = f"condition:{self.profile}:{self.seed}:{len(self.conditions):07d}"
        if condition_id in self.condition_ids:
            raise ValueError(f"Duplicate condition ID: {condition_id}")
        self.condition_ids.add(condition_id)
        self.conditions.append(
            {
                "condition_id": condition_id,
                "expression_json": stable_json(expression),
                "source_text": source_text,
            }
        )
        return condition_id

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        *,
        provider: str | None = None,
        effect: str = "ALLOW",
        scope: str | None = None,
        condition_id: str | None = None,
        direct: bool = True,
        relative_exploitability: float = 0.8,
        business_removal_cost: float = 1.0,
        removable: bool = True,
        protected: bool = False,
        source_artifact: str = "seib-2026-generator",
        edge_id: str | None = None,
    ) -> str:
        if source_id not in self.node_ids or target_id not in self.node_ids:
            raise ValueError(f"Unknown edge endpoint: {source_id} -> {target_id}")
        resolved_edge_id = edge_id or (f"edge:{self.profile}:{self.seed}:{self.edge_counter:09d}")
        self.edge_counter += 1
        if resolved_edge_id in self.edge_ids:
            raise ValueError(f"Duplicate edge ID: {resolved_edge_id}")
        self.edge_ids.add(resolved_edge_id)
        source = self.node_by_id[source_id]
        self.edges.append(
            {
                "edge_id": resolved_edge_id,
                "source_id": source_id,
                "target_id": target_id,
                "edge_type": edge_type,
                "provider": provider or str(source["provider"]),
                "effect": effect,
                "scope": scope or target_id,
                "condition_id": condition_id,
                "direct": direct,
                "derived": False,
                "derivation_rule": None,
                "confidence": 1.0,
                "relative_exploitability": max(1e-6, min(1.0, relative_exploitability)),
                "business_removal_cost": max(0.01, business_removal_cost),
                "removable": False if protected else removable,
                "protected": protected,
                "active": True,
                "valid_from": None,
                "valid_until": None,
                "source_artifact": source_artifact,
            }
        )
        return resolved_edge_id

    def sample(self, values: list[str]) -> str:
        if not values:
            raise ValueError("Cannot sample an empty collection")
        return values[int(self.rng.integers(0, len(values)))]

    def random_cost(self, *, protected: bool = False) -> float:
        base = float(self.rng.lognormal(mean=0.2, sigma=0.75))
        return round(base + (8.0 if protected else 0.0), 6)


def config_and_lock_hash(config_path: Path, lock_path: Path = Path("uv.lock")) -> tuple[str, str]:
    return sha256_file(config_path), sha256_file(lock_path)
