"""Truth-separated detection and ranking metrics."""

import json
import math
from collections.abc import Sequence
from typing import cast

import polars as pl
from pydantic import Field

from graphtrust.schemas.base import StrictModel
from graphtrust.schemas.findings import PathFinding


class DetectionMetrics(StrictModel):
    exact_path_precision: float = Field(ge=0, le=1)
    exact_path_recall: float = Field(ge=0, le=1)
    exact_path_f1: float = Field(ge=0, le=1)
    scenario_precision: float = Field(ge=0, le=1)
    scenario_recall: float = Field(ge=0, le=1)
    scenario_f1: float = Field(ge=0, le=1)
    risky_starting_identity_recall: float = Field(ge=0, le=1)
    critical_target_coverage: float = Field(ge=0, le=1)
    unmatched_findings_per_1000_identities: float = Field(ge=0)
    recall_at_5: float = Field(ge=0, le=1)
    recall_at_10: float = Field(ge=0, le=1)
    recall_at_20: float = Field(ge=0, le=1)
    recall_at_50: float = Field(ge=0, le=1)
    precision_at_5: float = Field(ge=0, le=1)
    precision_at_10: float = Field(ge=0, le=1)
    precision_at_20: float = Field(ge=0, le=1)
    precision_at_50: float = Field(ge=0, le=1)
    ndcg_at_10: float = Field(ge=0, le=1)
    ndcg_at_20: float = Field(ge=0, le=1)
    mean_reciprocal_rank: float = Field(ge=0, le=1)
    exact_true_positives: int = Field(ge=0)
    predicted_findings: int = Field(ge=0)
    truth_paths: int = Field(ge=0)
    unreviewed_prediction_count: int = Field(ge=0)


def _f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def _raw_signature(finding: PathFinding) -> tuple[str, ...]:
    return tuple(raw_id for step in finding.path for raw_id in step.raw_evidence_edge_ids)


def _dcg(relevances: Sequence[float]) -> float:
    return sum(
        (2**relevance - 1) / math.log2(index + 2) for index, relevance in enumerate(relevances)
    )


def evaluate_detection(
    findings: Sequence[PathFinding],
    truth_paths: pl.DataFrame,
    truth_scenarios: pl.DataFrame,
    *,
    identity_count: int,
) -> DetectionMetrics:
    """Join predictions to truth only after inference has completed."""
    truth_records = truth_paths.iter_rows(named=True)
    truth_by_signature: dict[tuple[str, ...], dict[str, object]] = {}
    truth_pairs: set[tuple[str, str]] = set()
    truth_sources: set[str] = set()
    truth_targets: set[str] = set()
    for row in truth_records:
        signature = tuple(str(value) for value in json.loads(str(row["edge_ids_json"])))
        truth_by_signature[signature] = row
        source_id = str(row["source_id"])
        target_id = str(row["target_id"])
        truth_pairs.add((source_id, target_id))
        truth_sources.add(source_id)
        truth_targets.add(target_id)

    positive_scenarios = {
        str(row["scenario_id"])
        for row in truth_scenarios.iter_rows(named=True)
        if not bool(row.get("is_hard_negative", False))
    }
    matched_signatures: set[tuple[str, ...]] = set()
    matched_scenarios: set[str] = set()
    matched_sources: set[str] = set()
    matched_targets: set[str] = set()
    relevance_by_rank: list[float] = []
    first_rank_by_scenario: dict[str, int] = {}
    unmatched = 0

    for rank, finding in enumerate(findings, start=1):
        signature = _raw_signature(finding)
        exact = truth_by_signature.get(signature)
        if exact is not None and (
            str(exact["source_id"]) != finding.source_identity_id
            or str(exact["target_id"]) != finding.target_asset_id
        ):
            exact = None
        pair_matched = (finding.source_identity_id, finding.target_asset_id) in truth_pairs
        if exact is not None:
            matched_signatures.add(signature)
            scenario_id = str(exact["scenario_id"])
            matched_scenarios.add(scenario_id)
            matched_sources.add(finding.source_identity_id)
            matched_targets.add(finding.target_asset_id)
            relevance = cast(float, exact["severity"])
            first_rank_by_scenario.setdefault(scenario_id, rank)
        else:
            relevance = 0.0
            if pair_matched:
                matching_scenarios = {
                    str(row["scenario_id"])
                    for row in truth_by_signature.values()
                    if str(row["source_id"]) == finding.source_identity_id
                    and str(row["target_id"]) == finding.target_asset_id
                }
                matched_scenarios.update(matching_scenarios)
                matched_sources.add(finding.source_identity_id)
                matched_targets.add(finding.target_asset_id)
            else:
                unmatched += 1
        relevance_by_rank.append(relevance)

    exact_tp = len(matched_signatures)
    prediction_count = len(findings)
    truth_count = len(truth_by_signature)
    exact_precision = exact_tp / prediction_count if prediction_count else 0.0
    exact_recall = exact_tp / truth_count if truth_count else 0.0
    scenario_tp = len(matched_scenarios.intersection(positive_scenarios))
    predicted_scenario_pairs = {
        (finding.source_identity_id, finding.target_asset_id) for finding in findings
    }
    matched_prediction_pairs = predicted_scenario_pairs.intersection(truth_pairs)
    scenario_precision = (
        len(matched_prediction_pairs) / len(predicted_scenario_pairs)
        if predicted_scenario_pairs
        else 0.0
    )
    scenario_recall = scenario_tp / len(positive_scenarios) if positive_scenarios else 0.0

    def recall_at(k: int) -> float:
        retained = {
            _raw_signature(finding)
            for finding in findings[:k]
            if _raw_signature(finding) in truth_by_signature
        }
        return len(retained) / truth_count if truth_count else 0.0

    def precision_at(k: int) -> float:
        if not findings:
            return 0.0
        retained = {
            _raw_signature(finding)
            for finding in findings[:k]
            if _raw_signature(finding) in truth_by_signature
        }
        return len(retained) / min(k, len(findings))

    ideal_relevances = sorted(
        (cast(float, row["severity"]) for row in truth_by_signature.values()), reverse=True
    )

    def ndcg_at(k: int) -> float:
        ideal = _dcg(ideal_relevances[:k])
        return _dcg(relevance_by_rank[:k]) / ideal if ideal else 0.0

    reciprocal_ranks = [
        1.0 / first_rank_by_scenario[scenario_id] if scenario_id in first_rank_by_scenario else 0.0
        for scenario_id in sorted(positive_scenarios)
    ]
    return DetectionMetrics(
        exact_path_precision=exact_precision,
        exact_path_recall=exact_recall,
        exact_path_f1=_f1(exact_precision, exact_recall),
        scenario_precision=scenario_precision,
        scenario_recall=scenario_recall,
        scenario_f1=_f1(scenario_precision, scenario_recall),
        risky_starting_identity_recall=(
            len(matched_sources) / len(truth_sources) if truth_sources else 0.0
        ),
        critical_target_coverage=(
            len(matched_targets) / len(truth_targets) if truth_targets else 0.0
        ),
        unmatched_findings_per_1000_identities=(
            unmatched * 1000.0 / identity_count if identity_count else 0.0
        ),
        recall_at_5=recall_at(5),
        recall_at_10=recall_at(10),
        recall_at_20=recall_at(20),
        recall_at_50=recall_at(50),
        precision_at_5=precision_at(5),
        precision_at_10=precision_at(10),
        precision_at_20=precision_at(20),
        precision_at_50=precision_at(50),
        ndcg_at_10=ndcg_at(10),
        ndcg_at_20=ndcg_at(20),
        mean_reciprocal_rank=(
            sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0
        ),
        exact_true_positives=exact_tp,
        predicted_findings=prediction_count,
        truth_paths=truth_count,
        unreviewed_prediction_count=unmatched,
    )
