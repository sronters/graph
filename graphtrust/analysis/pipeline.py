"""Truth-hidden dataset compilation and multi-method analysis pipeline."""

import gc
from dataclasses import dataclass

from graphtrust.analysis.runner import AnalysisLimits, AnalysisResult, run_analysis_methods
from graphtrust.data.conversion import CanonicalRecords, bundle_to_records
from graphtrust.data.io import DatasetBundle
from graphtrust.schemas.findings import AnalysisMethod
from graphtrust.semantics.compiler import CompilationResult, SemanticCompiler
from graphtrust.settings import ProjectConfig


@dataclass(frozen=True, slots=True)
class DatasetAnalysis:
    records: CanonicalRecords
    compilation: CompilationResult
    results: dict[AnalysisMethod, AnalysisResult]


def analyze_bundle(
    bundle: DatasetBundle,
    config: ProjectConfig,
    methods: tuple[AnalysisMethod, ...],
) -> DatasetAnalysis:
    """Compile raw semantics, then run methods without exposing benchmark truth."""
    # Preserve the dataset timestamp before we do anything else; we need it
    # even after we release the Polars frames.
    evaluated_at = bundle.manifest.generated_at

    records = bundle_to_records(
        bundle,
        criticality_threshold=config.analysis.criticality_threshold,
    )
    # The Polars DataFrames inside `bundle` (nodes, edges, conditions, assets,
    # truth_* …) are now fully materialised into `records` as Pydantic tuples.
    # On a 2.5 M-edge large profile these frames occupy several GiB; releasing
    # the caller's reference here — while keeping `records` which holds only
    # what compilation needs — prevents the raw Polars data and the Pydantic
    # objects from coexisting in memory at the same time.
    #
    # NOTE: this only frees the local alias.  If the *caller* also holds a
    # reference to the same bundle object the frames will remain live until the
    # caller drops theirs.  run_experiment_unit() is the hot path on Kaggle and
    # it explicitly drops the bundle and calls gc.collect() after this function
    # returns, which is the right place to do it (it needs truth_paths /
    # truth_scenarios from the bundle after we return).
    del bundle
    gc.collect()

    compiler = SemanticCompiler(
        condition_mode=config.condition_mode,
        evaluated_at=evaluated_at,
        include_disabled=config.analysis.include_disabled,
    )
    compilation = compiler.compile(records.nodes, records.edges, records.conditions)

    # After compilation the raw GraphEdge / Condition tuples are no longer
    # needed; only effective_edges, nodes, and critical_asset_ids are used by
    # the analysis runner.  Releasing them now roughly halves the live heap
    # before the igraph backend is constructed.
    raw_nodes = records.nodes
    critical_asset_ids = records.critical_asset_ids
    raw_edges_for_return = records.edges  # kept for remediation / API callers
    del records
    gc.collect()

    limits = AnalysisLimits(
        maximum_depth=config.analysis.maximum_depth,
        top_k_per_source_target=config.analysis.top_k_per_source_target,
        top_k_per_source=config.analysis.top_k_per_source,
        global_path_cap=config.analysis.global_path_cap,
        per_source_target_expansion_cap=config.analysis.per_source_target_expansion_cap,
        maximum_sources=config.analysis.maximum_sources,
        maximum_targets=config.analysis.maximum_targets,
    )
    results = run_analysis_methods(
        raw_nodes,
        compilation.effective_edges,
        critical_asset_ids,
        methods=methods,
        limits=limits,
        backend_name=config.backend,
    )
    # Reconstruct CanonicalRecords with the original raw_edges so that callers
    # that need analysis.records.edges (e.g. remediation/factory.py) still work.
    # conditions are not needed downstream so we omit them to save memory.
    return DatasetAnalysis(
        records=CanonicalRecords(
            nodes=raw_nodes,
            edges=raw_edges_for_return,
            conditions=(),
            critical_asset_ids=critical_asset_ids,
        ),
        compilation=compilation,
        results=results,
    )
