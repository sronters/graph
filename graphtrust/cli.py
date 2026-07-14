"""Command-line entry point for GraphTrust."""

from typing import Annotated

import typer

from graphtrust import __version__

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


if __name__ == "__main__":
    app()
