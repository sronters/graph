"""Truth-separated detection and ranking metric tests."""

import polars as pl
import pytest

from graphtrust.analysis.runner import AnalysisLimits, run_analysis_methods
from graphtrust.experiments.metrics import evaluate_detection
from graphtrust.schemas.findings import AnalysisMethod
from tests.unit.test_analysis import analysis_fixture


def test_detection_metrics_match_exact_truth_signature() -> None:
    nodes, edges = analysis_fixture()
    result = run_analysis_methods(
        nodes,
        edges,
        ("asset",),
        methods=(AnalysisMethod.DIRECT,),
        limits=AnalysisLimits(maximum_depth=2, top_k_per_source_target=5),
    )[AnalysisMethod.DIRECT]
    matching = next(
        finding
        for finding in result.findings
        if finding.source_identity_id == "low" and len(finding.path) == 1
    )
    truth_paths = pl.DataFrame(
        [
            {
                "path_id": "truth:1",
                "scenario_id": "scenario:1",
                "source_id": "low",
                "target_id": "asset",
                "edge_ids_json": '["raw:effective:direct"]',
                "severity": 0.9,
                "expected_detector_scope": "direct",
            }
        ]
    )
    truth_scenarios = pl.DataFrame(
        [
            {
                "scenario_id": "scenario:1",
                "is_hard_negative": False,
            }
        ]
    )
    metrics = evaluate_detection(
        (matching,),
        truth_paths,
        truth_scenarios,
        identity_count=2,
    )
    assert metrics.exact_path_precision == 1
    assert metrics.exact_path_recall == 1
    assert metrics.exact_path_f1 == 1
    assert metrics.scenario_recall == 1
    assert metrics.recall_at_5 == 1
    assert metrics.ndcg_at_10 == pytest.approx(1)
    assert metrics.mean_reciprocal_rank == 1


def test_empty_predictions_are_reported_without_division_errors() -> None:
    truth_paths = pl.DataFrame(
        schema={
            "path_id": pl.String,
            "scenario_id": pl.String,
            "source_id": pl.String,
            "target_id": pl.String,
            "edge_ids_json": pl.String,
            "severity": pl.Float64,
        }
    )
    truth_scenarios = pl.DataFrame(
        schema={"scenario_id": pl.String, "is_hard_negative": pl.Boolean}
    )
    metrics = evaluate_detection((), truth_paths, truth_scenarios, identity_count=0)
    assert metrics.predicted_findings == 0
    assert metrics.exact_path_precision == 0
    assert metrics.mean_reciprocal_rank == 0


def test_scenario_pair_match_does_not_fabricate_exact_path_match() -> None:
    nodes, edges = analysis_fixture()
    finding = run_analysis_methods(
        nodes,
        edges,
        ("asset",),
        methods=(AnalysisMethod.DIRECT,),
        limits=AnalysisLimits(maximum_depth=2),
    )[AnalysisMethod.DIRECT].findings[0]
    changed_step = finding.path[0].model_copy(update={"raw_evidence_edge_ids": ("raw:different",)})
    scenario_only = finding.model_copy(update={"path": (changed_step,)})
    truth_paths = pl.DataFrame(
        [
            {
                "path_id": "truth:1",
                "scenario_id": "scenario:1",
                "source_id": finding.source_identity_id,
                "target_id": finding.target_asset_id,
                "edge_ids_json": '["raw:expected"]',
                "severity": 0.8,
            }
        ]
    )
    truth_scenarios = pl.DataFrame([{"scenario_id": "scenario:1", "is_hard_negative": False}])
    metrics = evaluate_detection((scenario_only,), truth_paths, truth_scenarios, identity_count=2)
    assert metrics.exact_path_recall == 0
    assert metrics.scenario_recall == 1
    assert metrics.scenario_precision == 1
