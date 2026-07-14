"""Run preregistered ablations and sensitivity analysis for one dataset."""

import argparse
from pathlib import Path

from graphtrust.experiments.extended import run_extended_evaluation
from graphtrust.settings import load_project_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/extended"))
    arguments = parser.parse_args()
    destination = run_extended_evaluation(
        arguments.dataset,
        load_project_config(arguments.config),
        arguments.output,
    )
    print(destination)


if __name__ == "__main__":
    main()
