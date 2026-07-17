"""Tests for the lightweight large-run scheduler metadata path."""

import importlib.util
from pathlib import Path

from graphtrust.data.io import write_dataset
from tests.integration.test_dataset_io import small_bundle


def _large_profiles_module():
    path = Path("scripts/run_large_profiles.py")
    spec = importlib.util.spec_from_file_location("run_large_profiles", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_large_runner_reads_only_verified_dataset_provenance(tmp_path: Path) -> None:
    written = write_dataset(small_bundle(), tmp_path / "dataset")

    dataset_id, checksum, realized_counts = _large_profiles_module().read_dataset_provenance(
        tmp_path / "dataset"
    )

    assert dataset_id == written.manifest.dataset_id
    assert checksum == written.tree_checksum
    assert realized_counts == written.manifest.realized_counts
