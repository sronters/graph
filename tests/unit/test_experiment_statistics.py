"""Preregistered statistics, ablation, and sensitivity tests."""

import numpy as np
import pytest

from graphtrust.experiments.ablation import ABLATIONS, reweight_identity_score
from graphtrust.experiments.sensitivity import (
    dirichlet_weight_samples,
    rank_stability,
    vary_one_weight,
)
from graphtrust.experiments.statistics import (
    friedman_with_holm_wilcoxon,
    mcnemar_exact,
    paired_bootstrap_summary,
)
from graphtrust.schemas.findings import IdentityRiskScore


def test_paired_bootstrap_is_deterministic_and_paired() -> None:
    treatment = np.array([0.8, 0.9, 0.7, 1.0])
    baseline = np.array([0.5, 0.7, 0.6, 0.8])
    first = paired_bootstrap_summary(treatment, baseline, resamples=1_000, seed=7)
    second = paired_bootstrap_summary(treatment, baseline, resamples=1_000, seed=7)
    assert first == second
    assert first.mean_difference == pytest.approx(0.2)
    assert first.confidence_interval_95[0] > 0


def test_binary_and_multi_method_tests_report_effects() -> None:
    binary = mcnemar_exact(
        np.array([True, True, True, False]),
        np.array([False, False, True, True]),
    )
    assert binary["discordant"] == 3
    comparison = friedman_with_holm_wilcoxon(
        {
            "a": np.array([1.0, 2.0, 3.0, 4.0]),
            "b": np.array([2.0, 3.0, 4.0, 5.0]),
            "c": np.array([3.0, 4.0, 5.0, 6.0]),
        }
    )
    assert len(comparison["pairwise"]) == 3  # type: ignore[arg-type]


def test_sensitivity_sampling_and_rank_stability() -> None:
    samples = dirichlet_weight_samples(samples=1_000, seed=11)
    assert samples.shape == (1_000, 5)
    assert np.allclose(samples.sum(axis=1), 1)
    varied = vary_one_weight(np.array([0.3, 0.3, 0.15, 0.15, 0.1]), 0, 1.2)
    assert varied.sum() == pytest.approx(1)
    stability = rank_stability({"a": 3, "b": 2, "c": 1}, {"a": 4, "b": 2, "c": 0})
    assert stability == {"spearman": 1.0, "top_k_jaccard": 1.0}


def test_all_seven_ablation_definitions_and_score_reweighting() -> None:
    assert len(ABLATIONS) == 7
    assert len({ablation.name for ablation in ABLATIONS}) == 7
    score = IdentityRiskScore(
        node_id="identity:1",
        critical_reach=1,
        best_path=0.8,
        path_diversity=0.6,
        blast_radius=0.4,
        control_weakness=0.2,
        ztri=70,
    )
    assert reweight_identity_score(score, "no_path_diversity").ztri != score.ztri
    assert reweight_identity_score(score, "equal_ztri_weights").ztri == pytest.approx(60)
