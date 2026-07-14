"""Preregistered ablation and sensitivity execution over one verified dataset."""

import json
import subprocess
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np

from graphtrust.analysis.pipeline import analyze_bundle
from graphtrust.analysis.runner import AnalysisLimits, run_analysis_methods
from graphtrust.data import read_dataset
from graphtrust.data.checksums import sha256_bytes, write_checksum_file
from graphtrust.experiments.ablation import (
    ABLATIONS,
    reweight_identity_score,
    transform_graph_for_ablation,
)
from graphtrust.experiments.metrics import evaluate_detection
from graphtrust.experiments.sensitivity import (
    SensitivityRegistry,
    dirichlet_weight_samples,
    rank_stability,
    vary_one_weight,
)
from graphtrust.remediation.constraint_generation import solve_with_constraint_generation
from graphtrust.remediation.factory import build_remediation_problem
from graphtrust.schemas.findings import AnalysisMethod, IdentityRiskScore
from graphtrust.settings import ProjectConfig


def _json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _score_values(score: IdentityRiskScore) -> np.ndarray:
    return np.array(
        [
            score.critical_reach,
            score.best_path,
            score.path_diversity,
            score.blast_radius,
            score.control_weakness,
        ]
    )


def _weighted_scores(
    scores: tuple[IdentityRiskScore, ...], weights: np.ndarray
) -> dict[str, float]:
    return {score.node_id: float(100 * np.dot(_score_values(score), weights)) for score in scores}


def _metrics(
    findings: tuple[Any, ...],
    bundle: Any,
    identity_count: int,
) -> dict[str, Any]:
    return evaluate_detection(
        findings,
        bundle.truth_paths,
        bundle.truth_scenarios,
        identity_count=identity_count,
    ).model_dump(mode="json")


def run_extended_evaluation(
    dataset_path: Path,
    config: ProjectConfig,
    output_root: Path,
) -> Path:
    """Run all seven ablations and the declared rank-sensitivity registry."""
    bundle = read_dataset(dataset_path)
    config_json = json.dumps(config.model_dump(mode="json"), sort_keys=True)
    run_material = "\0".join(
        (bundle.tree_checksum or "", sha256_bytes(config_json.encode()), _git_commit())
    )
    destination = output_root / ("extended-" + sha256_bytes(run_material.encode())[:24])
    if (destination / "checksums.sha256").is_file():
        return destination
    destination.mkdir(parents=True, exist_ok=False)
    base = analyze_bundle(bundle, config, (AnalysisMethod.GRAPHTRUST,))
    base_result = base.results[AnalysisMethod.GRAPHTRUST]
    identity_count = sum(
        node.identity_status.value != "NOT_APPLICABLE" for node in base.records.nodes
    )
    base_metrics = _metrics(base_result.findings, bundle, identity_count)

    ablations: list[dict[str, Any]] = []
    for spec in ABLATIONS:
        if spec.name in {"no_path_diversity", "equal_ztri_weights"}:
            scores = tuple(
                reweight_identity_score(score, spec.name) for score in base_result.identity_scores
            )
            metrics = base_metrics
            extra: dict[str, Any] = {"top_identity_ztri": scores[0].ztri if scores else 0.0}
        elif spec.name == "shortest_path_only":
            result = run_analysis_methods(
                base.records.nodes,
                base.compilation.effective_edges,
                base.records.critical_asset_ids,
                methods=(AnalysisMethod.GRAPHTRUST,),
                limits=AnalysisLimits(
                    maximum_depth=config.analysis.maximum_depth,
                    top_k_per_source_target=1,
                    top_k_per_source=config.analysis.top_k_per_source,
                    global_path_cap=config.analysis.global_path_cap,
                ),
                backend_name=config.backend,
            )[AnalysisMethod.GRAPHTRUST]
            metrics = _metrics(result.findings, bundle, identity_count)
            extra = {"findings": len(result.findings)}
        elif spec.name == "no_business_cost":
            problem = build_remediation_problem(dataset_path, config)
            equal_cost_edges = tuple(
                edge.model_copy(update={"business_removal_cost": 1.0}) for edge in problem.raw_edges
            )
            plan = solve_with_constraint_generation(
                replace(problem, raw_edges=equal_cost_edges),
                target_fraction=0.9,
                maximum_depth=config.analysis.maximum_depth,
            )
            metrics = base_metrics
            extra = {"remediation": plan.model_dump(mode="json")}
        else:
            nodes, edges = transform_graph_for_ablation(
                spec.name,
                base.records.nodes,
                base.compilation.effective_edges,
            )
            targets = tuple(
                target
                for target in base.records.critical_asset_ids
                if any(node.node_id == target for node in nodes)
            )
            result = run_analysis_methods(
                nodes,
                edges,
                targets,
                methods=(AnalysisMethod.GRAPHTRUST,),
                limits=AnalysisLimits(
                    maximum_depth=config.analysis.maximum_depth,
                    top_k_per_source_target=config.analysis.top_k_per_source_target,
                    top_k_per_source=config.analysis.top_k_per_source,
                    global_path_cap=config.analysis.global_path_cap,
                ),
                backend_name=config.backend,
            )[AnalysisMethod.GRAPHTRUST]
            metrics = _metrics(result.findings, bundle, identity_count)
            extra = {"findings": len(result.findings)}
        ablations.append(
            {
                "name": spec.name,
                "description": spec.description,
                "metrics": metrics,
                **extra,
            }
        )

    registry = SensitivityRegistry()
    reference_scores = {score.node_id: score.ztri for score in base_result.identity_scores}
    sensitivity: list[dict[str, Any]] = []

    def analyze_variant(name: str, value: object, varied_config: ProjectConfig) -> None:
        result = analyze_bundle(bundle, varied_config, (AnalysisMethod.GRAPHTRUST,)).results[
            AnalysisMethod.GRAPHTRUST
        ]
        comparison = {score.node_id: score.ztri for score in result.identity_scores}
        sensitivity.append(
            {"parameter": name, "value": value, **rank_stability(reference_scores, comparison)}
        )

    for depth in registry.maximum_depths:
        analyze_variant(
            "maximum_depth",
            depth,
            config.model_copy(
                update={"analysis": config.analysis.model_copy(update={"maximum_depth": depth})}
            ),
        )
    for threshold in registry.criticality_thresholds:
        analyze_variant(
            "criticality_threshold",
            threshold,
            config.model_copy(
                update={
                    "analysis": config.analysis.model_copy(
                        update={"criticality_threshold": threshold}
                    )
                }
            ),
        )
    for mode in registry.condition_modes:
        analyze_variant("condition_mode", mode, config.model_copy(update={"condition_mode": mode}))
    for cap in registry.top_k_caps:
        analyze_variant(
            "top_k_per_source_target",
            cap,
            config.model_copy(
                update={
                    "analysis": config.analysis.model_copy(update={"top_k_per_source_target": cap})
                }
            ),
        )

    for multiplier in registry.edge_parameter_multipliers:
        varied_edges = tuple(
            edge.model_copy(
                update={
                    "relative_exploitability": max(
                        1e-6, min(1.0, edge.relative_exploitability * multiplier)
                    )
                }
            )
            for edge in base.compilation.effective_edges
        )
        result = run_analysis_methods(
            base.records.nodes,
            varied_edges,
            base.records.critical_asset_ids,
            methods=(AnalysisMethod.GRAPHTRUST,),
            backend_name=config.backend,
        )[AnalysisMethod.GRAPHTRUST]
        comparison = {score.node_id: score.ztri for score in result.identity_scores}
        sensitivity.append(
            {
                "parameter": "edge_exploitability_multiplier",
                "value": multiplier,
                **rank_stability(reference_scores, comparison),
            }
        )

    primary_weights = np.array([0.30, 0.30, 0.15, 0.15, 0.10])
    for index, component in enumerate(
        ("critical_reach", "best_path", "path_diversity", "blast_radius", "control_weakness")
    ):
        for multiplier in (0.8, 1.2):
            weights = vary_one_weight(primary_weights, index, multiplier)
            sensitivity.append(
                {
                    "parameter": f"weight_{component}",
                    "value": multiplier,
                    **rank_stability(
                        reference_scores,
                        _weighted_scores(base_result.identity_scores, weights),
                    ),
                }
            )
    dirichlet_results = [
        rank_stability(
            reference_scores,
            _weighted_scores(base_result.identity_scores, weights),
        )
        for weights in dirichlet_weight_samples()
    ]

    _json(destination / "ablation_results.json", ablations)
    _json(
        destination / "sensitivity_results.json",
        {
            "one_at_a_time": sensitivity,
            "dirichlet_1000": dirichlet_results,
            "registry": asdict(registry),
        },
    )
    _json(
        destination / "extended_manifest.json",
        {
            "schema_version": "1.0",
            "dataset_id": bundle.manifest.dataset_id,
            "dataset_checksum": bundle.tree_checksum,
            "config_checksum": sha256_bytes(config_json.encode()),
            "git_commit": _git_commit(),
            "ablation_count": len(ablations),
            "dirichlet_sample_count": len(dirichlet_results),
        },
    )
    write_checksum_file(
        destination,
        ("ablation_results.json", "sensitivity_results.json", "extended_manifest.json"),
    )
    return destination
