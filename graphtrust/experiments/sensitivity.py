"""Deterministic sensitivity configuration and rank-stability utilities."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy import stats  # type: ignore[import-untyped]


@dataclass(frozen=True, slots=True)
class SensitivityRegistry:
    maximum_depths: tuple[int, ...] = tuple(range(4, 11))
    criticality_thresholds: tuple[float, ...] = (0.60, 0.70, 0.80, 0.90)
    top_k_caps: tuple[int, ...] = (5, 10, 20, 50)
    condition_modes: tuple[str, ...] = ("conservative", "strict")
    edge_parameter_multipliers: tuple[float, ...] = (0.8, 1.0, 1.2)


def dirichlet_weight_samples(
    *,
    samples: int = 1_000,
    seed: int = 104729,
    concentration: float = 100.0,
) -> NDArray[np.float64]:
    """Sample normalized ZTRI weights centered on the primary preregistered vector."""
    center = np.array([0.30, 0.30, 0.15, 0.15, 0.10], dtype=float)
    sampled: NDArray[np.float64] = np.random.default_rng(seed).dirichlet(
        center * concentration, size=samples
    )
    return sampled


def vary_one_weight(
    weights: np.ndarray,
    index: int,
    multiplier: float,
) -> NDArray[np.float64]:
    """Vary one component by plus or minus 20% and renormalize all weights."""
    values = np.asarray(weights, dtype=float).copy()
    if values.shape != (5,) or not 0 <= index < 5:
        raise ValueError("weights must have five components and index must be valid")
    values[index] *= multiplier
    normalized: NDArray[np.float64] = np.divide(values, values.sum())
    return normalized


def rank_stability(
    reference_scores: dict[str, float],
    comparison_scores: dict[str, float],
    *,
    top_k: int = 10,
) -> dict[str, float]:
    """Report Spearman correlation and top-K Jaccard overlap on shared identities."""
    shared = sorted(set(reference_scores).intersection(comparison_scores))
    if len(shared) < 2:
        spearman = 1.0 if shared else 0.0
    else:
        result = stats.spearmanr(
            [reference_scores[node_id] for node_id in shared],
            [comparison_scores[node_id] for node_id in shared],
        )
        spearman = 0.0 if np.isnan(result.statistic) else float(result.statistic)
    reference_top = {
        node_id
        for node_id, _ in sorted(reference_scores.items(), key=lambda item: (-item[1], item[0]))[
            :top_k
        ]
    }
    comparison_top = {
        node_id
        for node_id, _ in sorted(comparison_scores.items(), key=lambda item: (-item[1], item[0]))[
            :top_k
        ]
    }
    union = reference_top | comparison_top
    jaccard = len(reference_top & comparison_top) / len(union) if union else 1.0
    return {"spearman": spearman, "top_k_jaccard": jaccard}
