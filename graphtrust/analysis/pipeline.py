"""Truth-hidden dataset compilation and multi-method analysis pipeline."""

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
    records = bundle_to_records(bundle)
    compiler = SemanticCompiler(
        condition_mode=config.condition_mode,
        evaluated_at=bundle.manifest.generated_at,
        include_disabled=config.analysis.include_disabled,
    )
    compilation = compiler.compile(records.nodes, records.edges, records.conditions)
    limits = AnalysisLimits(
        maximum_depth=config.analysis.maximum_depth,
        top_k_per_source_target=config.analysis.top_k_per_source_target,
        top_k_per_source=config.analysis.top_k_per_source,
        global_path_cap=config.analysis.global_path_cap,
    )
    results = run_analysis_methods(
        records.nodes,
        compilation.effective_edges,
        records.critical_asset_ids,
        methods=methods,
        limits=limits,
        backend_name=config.backend,
    )
    return DatasetAnalysis(records=records, compilation=compilation, results=results)
