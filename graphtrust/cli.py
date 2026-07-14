"""Command-line entry point for GraphTrust."""

import json
from pathlib import Path
from typing import Annotated

import typer

from graphtrust import __version__
from graphtrust.data import read_dataset, validate_bundle
from graphtrust.generator.models import SCALE_SPECS
from graphtrust.generator.runner import SUPPORTED_VARIANTS, generate_dataset_suite

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
    for dataset in generated:
        typer.echo(
            json.dumps(
                {
                    "dataset_id": dataset.dataset_id,
                    "variant": dataset.variant,
                    "path": str(dataset.destination),
                    "tree_checksum": dataset.tree_checksum,
                    "nodes": dataset.node_count,
                    "edges": dataset.edge_count,
                    "scenarios": dataset.scenario_count,
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    app()
