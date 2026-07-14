"""Run one immutable GraphTrust analysis for each large SEIB-2026 profile."""

from __future__ import annotations

import argparse
import json
import os
import platform
from datetime import UTC, datetime
from pathlib import Path

from graphtrust.data import read_dataset
from graphtrust.experiments.registry import ExperimentUnit
from graphtrust.experiments.runner import run_experiment_unit, verify_run_directory
from graphtrust.schemas.findings import AnalysisMethod
from graphtrust.schemas.manifests import DatasetVariant
from graphtrust.settings import load_project_config

PROFILES = ("saas_scaleup", "regulated_finance", "global_hybrid")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("data/generated"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/large_runs"))
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--seed", type=int, default=2_750_159)
    parser.add_argument("--profile", choices=(*PROFILES, "all"), default="all")
    arguments = parser.parse_args()

    profiles = PROFILES if arguments.profile == "all" else (arguments.profile,)
    config = load_project_config(arguments.config)
    receipts: list[dict[str, object]] = []
    for profile in profiles:
        dataset = (
            arguments.data_root
            / profile
            / "large"
            / str(arguments.seed)
            / DatasetVariant.INJECTED_MIXED.value
        )
        bundle = read_dataset(dataset)
        unit = ExperimentUnit(
            dataset_path=dataset,
            dataset_id=bundle.manifest.dataset_id,
            profile=profile,
            scale="large",
            seed=arguments.seed,
            variant=DatasetVariant.INJECTED_MIXED,
            method=AnalysisMethod.GRAPHTRUST,
        )
        outcome = run_experiment_unit(unit, config, output_root=arguments.output, resume=True)
        valid, failures = verify_run_directory(outcome.run_directory)
        receipts.append(
            {
                "profile": profile,
                "dataset_id": bundle.manifest.dataset_id,
                "dataset_checksum": bundle.tree_checksum,
                "realized_counts": bundle.manifest.realized_counts,
                "run_id": outcome.run_id,
                "run_directory": str(outcome.run_directory),
                "status": outcome.status,
                "verified": valid,
                "verification_failures": failures,
            }
        )

    arguments.output.mkdir(parents=True, exist_ok=True)
    receipt = {
        "created_at": datetime.now(UTC).isoformat(),
        "is_google_colab": "COLAB_RELEASE_TAG" in os.environ,
        "colab_release_tag": os.getenv("COLAB_RELEASE_TAG"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "profiles": receipts,
    }
    path = arguments.output / "large_run_receipt.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
