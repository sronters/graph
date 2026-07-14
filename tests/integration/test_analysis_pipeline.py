"""Truth-hidden dataset compilation through both graph backends."""

from pathlib import Path

from typer.testing import CliRunner

from graphtrust.analysis.pipeline import analyze_bundle
from graphtrust.cli import app
from graphtrust.data.conversion import bundle_to_records
from graphtrust.data.io import write_dataset
from graphtrust.schemas.findings import AnalysisMethod
from graphtrust.settings import load_project_config
from tests.integration.test_dataset_io import small_bundle


def test_pipeline_ignores_truth_tables_during_inference() -> None:
    bundle = small_bundle()
    records = bundle_to_records(bundle)
    assert len(records.nodes) == 2
    assert len(records.edges) == 1
    assert records.critical_asset_ids == ("database:critical",)
    assert all(node.ground_truth_labels_json is None for node in records.nodes)
    assert all(edge.ground_truth_scenario_id is None for edge in records.edges)

    analysis = analyze_bundle(
        bundle,
        load_project_config(),
        (
            AnalysisMethod.DIRECT,
            AnalysisMethod.UNTYPED,
            AnalysisMethod.NATIVE_SCOPE,
            AnalysisMethod.GRAPHTRUST,
        ),
    )
    assert len(analysis.compilation.effective_edges) == 1
    assert all(result.findings for result in analysis.results.values())


def test_igraph_pipeline_matches_reference_finding_signatures() -> None:
    bundle = small_bundle()
    reference_config = load_project_config()
    scalable_config = reference_config.model_copy(update={"backend": "igraph"})
    methods = (AnalysisMethod.GRAPHTRUST,)
    reference = analyze_bundle(bundle, reference_config, methods)
    scalable = analyze_bundle(bundle, scalable_config, methods)
    reference_signatures = [
        tuple(raw for step in finding.path for raw in step.raw_evidence_edge_ids)
        for finding in reference.results[AnalysisMethod.GRAPHTRUST].findings
    ]
    scalable_signatures = [
        tuple(raw for step in finding.path for raw in step.raw_evidence_edge_ids)
        for finding in scalable.results[AnalysisMethod.GRAPHTRUST].findings
    ]
    assert scalable_signatures == reference_signatures


def test_analyze_cli_executes_real_fixture(tmp_path: Path) -> None:
    destination = tmp_path / "dataset"
    write_dataset(small_bundle(), destination)
    result = CliRunner().invoke(
        app,
        [
            "analyze",
            "--dataset",
            str(destination),
            "--methods",
            "direct,graphtrust",
            "--config",
            "configs/default.yaml",
        ],
    )
    assert result.exit_code == 0, result.output
    assert '"effective_edges": 1' in result.output
    assert '"graphtrust"' in result.output
