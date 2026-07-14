"""Command-line entry point for GraphTrust."""

import json
from pathlib import Path
from typing import Annotated

import typer

from graphtrust import __version__
from graphtrust.data import read_dataset, validate_bundle

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


if __name__ == "__main__":
    app()
