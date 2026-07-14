"""Command-line entry point for GraphTrust."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated

import typer

from graphtrust import __version__
from graphtrust.analysis.pipeline import analyze_bundle
from graphtrust.data import read_dataset, validate_bundle
from graphtrust.experiments.registry import ExperimentUnit, expand_registry, load_registry
from graphtrust.experiments.reporting import generate_report
from graphtrust.experiments.runner import ExperimentOutcome, run_experiment_unit
from graphtrust.generator.models import SCALE_SPECS
from graphtrust.generator.runner import SUPPORTED_VARIANTS, generate_dataset_suite
from graphtrust.schemas.findings import AnalysisMethod
from graphtrust.settings import load_project_config

app = typer.Typer(
    name="graphtrust",
    help="Explainable whole-identity graph analysis for defensive IAM research.",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    """Print the installed version and exit."""
    if value:
        typer.echo(__version__)
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """Run GraphTrust commands."""


@app.command("validate-data")
def validate_data(
    dataset: Annotated[Path, typer.Option("--dataset", exists=True, file_okay=False)],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    """Verify checksums, schema, truth separation, and referential integrity."""
    try:
        bundle = read_dataset(dataset)
        report = validate_bundle(bundle)
    except (FileNotFoundError, OSError, ValueError) as error:
        typer.echo(f"Dataset validation failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    payload = {
        "dataset_id": bundle.manifest.dataset_id,
        "tree_checksum": bundle.tree_checksum,
        "valid": report.valid,
        "errors": report.errors,
        "warnings": report.warnings,
        "counts": report.counts,
    }
    if json_output:
        typer.echo(json.dumps(payload, sort_keys=True))
    else:
        typer.echo(f"Dataset: {bundle.manifest.dataset_id}")
        typer.echo(f"Checksum: {bundle.tree_checksum}")
        typer.echo(f"Status: {'valid' if report.valid else 'invalid'}")
        for warning in report.warnings:
            typer.echo(f"Warning: {warning}")
        for validation_error in report.errors:
            typer.echo(f"Error: {validation_error}", err=True)
    if not report.valid:
        raise typer.Exit(code=1)


@app.command("generate")
def generate(
    profile: Annotated[str, typer.Option("--profile")],
    scale: Annotated[str, typer.Option("--scale")],
    seed: Annotated[int, typer.Option("--seed")],
    variants: Annotated[
        str,
        typer.Option(
            "--variants",
            help="Comma-separated paired variants.",
        ),
    ] = ",".join(SUPPORTED_VARIANTS),
    output_root: Annotated[
        Path,
        typer.Option("--output-root", file_okay=False),
    ] = Path("data/generated"),
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Generate deterministic paired SEIB-2026 datasets."""
    requested_variants = tuple(item.strip() for item in variants.split(",") if item.strip())
    try:
        if scale not in SCALE_SPECS:
            raise ValueError(f"Unsupported scale: {scale}")
        if dry_run:
            spec = SCALE_SPECS[scale]
            typer.echo(
                json.dumps(
                    {
                        "dry_run": True,
                        "profile": profile,
                        "scale": scale,
                        "seed": seed,
                        "variants": requested_variants,
                        "targets": {
                            "humans": spec.humans,
                            "non_humans": spec.non_humans,
                            "groups_and_roles": spec.groups + spec.roles,
                            "resources": spec.resources,
                            "raw_edges": spec.raw_edges,
                        },
                    },
                    sort_keys=True,
                )
            )
            return
        generated = generate_dataset_suite(
            profile=profile,
            scale=scale,
            seed=seed,
            variants=requested_variants,
            output_root=output_root,
        )
    except (FileExistsError, OSError, ValueError) as generation_error:
        typer.echo(f"Generation failed: {generation_error}", err=True)
        raise typer.Exit(code=1) from generation_error
    for generated_dataset in generated:
        typer.echo(
            json.dumps(
                {
                    "dataset_id": generated_dataset.dataset_id,
                    "variant": generated_dataset.variant,
                    "path": str(generated_dataset.destination),
                    "tree_checksum": generated_dataset.tree_checksum,
                    "nodes": generated_dataset.node_count,
                    "edges": generated_dataset.edge_count,
                    "scenarios": generated_dataset.scenario_count,
                },
                sort_keys=True,
            )
        )


@app.command("analyze")
def analyze(
    dataset: Annotated[Path, typer.Option("--dataset", exists=True, file_okay=False)],
    methods: Annotated[
        str,
        typer.Option(
            "--methods",
            help="Comma-separated methods: direct, privileged, untyped, native_scope, graphtrust.",
        ),
    ] = ",".join(method.value for method in AnalysisMethod),
    config: Annotated[
        Path,
        typer.Option("--config", exists=True, dir_okay=False),
    ] = Path("configs/default.yaml"),
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Compile IAM semantics and run truth-hidden analysis methods."""
    try:
        selected_methods = tuple(
            AnalysisMethod(item.strip()) for item in methods.split(",") if item.strip()
        )
        if not selected_methods:
            raise ValueError("At least one analysis method is required")
        if len(set(selected_methods)) != len(selected_methods):
            raise ValueError("Analysis methods must be unique")
        bundle = read_dataset(dataset)
        project_config = load_project_config(config)
        if dry_run:
            typer.echo(
                json.dumps(
                    {
                        "dry_run": True,
                        "dataset_id": bundle.manifest.dataset_id,
                        "methods": [method.value for method in selected_methods],
                        "backend": project_config.backend,
                        "maximum_depth": project_config.analysis.maximum_depth,
                    },
                    sort_keys=True,
                )
            )
            return
        analysis = analyze_bundle(bundle, project_config, selected_methods)
    except (FileNotFoundError, OSError, ValueError) as analysis_error:
        typer.echo(f"Analysis failed: {analysis_error}", err=True)
        raise typer.Exit(code=1) from analysis_error
    typer.echo(
        json.dumps(
            {
                "dataset_id": bundle.manifest.dataset_id,
                "effective_edges": len(analysis.compilation.effective_edges),
                "rejected_semantic_edges": len(analysis.compilation.rejected_edges),
                "methods": {
                    method.value: {
                        "findings": len(result.findings),
                        "risky_starting_identities": len(result.reachability),
                        "search_complete": result.search_complete,
                        "expanded_states": result.expanded_states,
                    }
                    for method, result in analysis.results.items()
                },
            },
            sort_keys=True,
        )
    )


@app.command("experiment")
def experiment(
    registry: Annotated[
        Path,
        typer.Option("--registry", exists=True, dir_okay=False),
    ] = Path("configs/experiments.yaml"),
    workers: Annotated[str, typer.Option("--workers")] = "auto",
    resume: Annotated[bool, typer.Option("--resume")] = False,
    config: Annotated[
        Path,
        typer.Option("--config", exists=True, dir_okay=False),
    ] = Path("configs/default.yaml"),
    data_root: Annotated[
        Path,
        typer.Option("--data-root", file_okay=False),
    ] = Path("data/generated"),
    output_root: Annotated[
        Path,
        typer.Option("--output-root", file_okay=False),
    ] = Path("artifacts/manifests"),
    include_development: Annotated[
        bool,
        typer.Option("--include-development"),
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Run the registered matrix with immutable, resumable artifacts."""
    try:
        declared = load_registry(registry)
        expansion = expand_registry(
            declared,
            data_root=data_root,
            include_development=include_development,
        )
        project_config = load_project_config(config)
        worker_count = min(4, os.cpu_count() or 1) if workers == "auto" else int(workers)
        if worker_count < 1:
            raise ValueError("workers must be 'auto' or a positive integer")
        if dry_run:
            typer.echo(
                json.dumps(
                    {
                        "dry_run": True,
                        "scheduled_runs": len(expansion.units),
                        "missing_datasets": expansion.missing_datasets,
                        "workers": worker_count,
                    },
                    sort_keys=True,
                )
            )
            return

        def execute(unit: ExperimentUnit) -> ExperimentOutcome:
            return run_experiment_unit(
                unit,
                project_config,
                output_root=output_root,
                resume=resume,
            )

        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            outcomes = tuple(pool.map(execute, expansion.units))
    except (FileNotFoundError, OSError, TypeError, ValueError) as experiment_error:
        typer.echo(f"Experiment failed: {experiment_error}", err=True)
        raise typer.Exit(code=1) from experiment_error
    typer.echo(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": outcome.run_id,
                        "status": outcome.status,
                        "directory": str(outcome.run_directory),
                    }
                    for outcome in outcomes
                ],
                "missing_datasets": expansion.missing_datasets,
            },
            sort_keys=True,
        )
    )


@app.command("report")
def report(
    runs: Annotated[
        Path,
        typer.Option("--runs", exists=True, file_okay=False),
    ] = Path("artifacts/manifests"),
    output: Annotated[
        Path,
        typer.Option("--output", file_okay=False),
    ] = Path("artifacts/paper"),
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Build traceable tables from verified experiment artifacts only."""
    if dry_run:
        typer.echo(json.dumps({"dry_run": True, "runs": str(runs), "output": str(output)}))
        return
    try:
        payload = generate_report(runs, output)
    except (FileNotFoundError, OSError, ValueError) as report_error:
        typer.echo(f"Report generation failed: {report_error}", err=True)
        raise typer.Exit(code=1) from report_error
    typer.echo(
        json.dumps(
            {
                "verified_runs": len(payload["verified_run_ids"]),
                "output": str(output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    app()
