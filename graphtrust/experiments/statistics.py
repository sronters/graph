"""Paired uncertainty, effect sizes, and preregistered nonparametric tests."""

import itertools
from dataclasses import dataclass

import numpy as np
from scipy import stats  # type: ignore[import-untyped]


@dataclass(frozen=True, slots=True)
class PairedSummary:
    count: int
    median_difference: float
    mean_difference: float
    q1_difference: float
    q3_difference: float
    confidence_interval_95: tuple[float, float]
    standardized_mean_effect: float


def paired_bootstrap_summary(
    treatment: np.ndarray,
    baseline: np.ndarray,
    *,
    resamples: int = 10_000,
    seed: int = 104729,
) -> PairedSummary:
    """Summarize paired graph-level differences with a paired bootstrap CI."""
    treatment = np.asarray(treatment, dtype=float)
    baseline = np.asarray(baseline, dtype=float)
    if treatment.shape != baseline.shape or treatment.ndim != 1:
        raise ValueError("treatment and baseline must be equal-length one-dimensional arrays")
    if treatment.size == 0:
        raise ValueError("paired samples must not be empty")
    differences = treatment - baseline
    rng = np.random.default_rng(seed)
    indexes = rng.integers(0, differences.size, size=(resamples, differences.size))
    bootstrap_means = differences[indexes].mean(axis=1)
    lower, upper = np.quantile(bootstrap_means, (0.025, 0.975))
    standard_deviation = float(differences.std(ddof=1)) if differences.size > 1 else 0.0
    effect = float(differences.mean() / standard_deviation) if standard_deviation else 0.0
    return PairedSummary(
        count=int(differences.size),
        median_difference=float(np.median(differences)),
        mean_difference=float(differences.mean()),
        q1_difference=float(np.quantile(differences, 0.25)),
        q3_difference=float(np.quantile(differences, 0.75)),
        confidence_interval_95=(float(lower), float(upper)),
        standardized_mean_effect=effect,
    )


def mcnemar_exact(
    treatment_detected: np.ndarray,
    baseline_detected: np.ndarray,
) -> dict[str, float | int]:
    """Exact two-sided McNemar test on paired binary scenario outcomes."""
    treatment = np.asarray(treatment_detected, dtype=bool)
    baseline = np.asarray(baseline_detected, dtype=bool)
    if treatment.shape != baseline.shape or treatment.ndim != 1:
        raise ValueError("paired outcomes must have the same one-dimensional shape")
    treatment_only = int(np.sum(treatment & ~baseline))
    baseline_only = int(np.sum(~treatment & baseline))
    discordant = treatment_only + baseline_only
    p_value = (
        float(stats.binomtest(min(treatment_only, baseline_only), discordant, 0.5).pvalue)
        if discordant
        else 1.0
    )
    return {
        "treatment_only": treatment_only,
        "baseline_only": baseline_only,
        "discordant": discordant,
        "p_value": p_value,
    }


def friedman_with_holm_wilcoxon(
    methods: dict[str, np.ndarray],
) -> dict[str, object]:
    """Friedman omnibus test and Holm-corrected paired Wilcoxon follow-ups."""
    if len(methods) < 3:
        raise ValueError("Friedman comparison requires at least three methods")
    names = sorted(methods)
    arrays = [np.asarray(methods[name], dtype=float) for name in names]
    shapes = {array.shape for array in arrays}
    if len(shapes) != 1 or arrays[0].ndim != 1 or arrays[0].size < 2:
        raise ValueError("method arrays must be equal-length one-dimensional paired samples")
    statistic, omnibus_p = stats.friedmanchisquare(*arrays)
    raw_pairs: list[tuple[tuple[str, str], float, float]] = []
    for left, right in itertools.combinations(names, 2):
        difference = methods[left] - methods[right]
        if np.allclose(difference, 0):
            p_value = 1.0
        else:
            result = stats.wilcoxon(methods[left], methods[right], alternative="two-sided")
            p_value = float(result.pvalue)
        nonzero = difference[difference != 0]
        rank_biserial = (
            float((np.sum(nonzero > 0) - np.sum(nonzero < 0)) / nonzero.size)
            if nonzero.size
            else 0.0
        )
        raw_pairs.append(((left, right), p_value, rank_biserial))
    ordered = sorted(raw_pairs, key=lambda item: item[1])
    corrected: dict[tuple[str, str], float] = {}
    running = 0.0
    total = len(ordered)
    for index, (pair, p_value, _) in enumerate(ordered):
        running = max(running, min(1.0, p_value * (total - index)))
        corrected[pair] = running
    return {
        "friedman_statistic": float(statistic),
        "friedman_p_value": float(omnibus_p),
        "pairwise": [
            {
                "left": pair[0],
                "right": pair[1],
                "raw_p_value": p_value,
                "holm_p_value": corrected[pair],
                "rank_biserial_effect": effect,
            }
            for pair, p_value, effect in raw_pairs
        ],
    }
