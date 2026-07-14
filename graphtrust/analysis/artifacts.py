"""Small mutable pointer to the latest reproducible analysis inputs."""

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from graphtrust.data.io import DatasetBundle
from graphtrust.schemas.findings import AnalysisMethod
from graphtrust.settings import ProjectConfig


def write_latest_analysis_index(
    destination: Path,
    *,
    dataset_path: Path,
    config_path: Path,
    bundle: DatasetBundle,
    config: ProjectConfig,
    methods: tuple[AnalysisMethod, ...],
) -> Path:
    """Atomically replace a convenience pointer; immutable experiments remain separate."""
    payload = {
        "schema_version": "1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_id": bundle.manifest.dataset_id,
        "dataset_path": str(dataset_path.resolve()),
        "dataset_checksum": bundle.tree_checksum,
        "config_path": str(config_path.resolve()),
        "resolved_config": config.model_dump(mode="json"),
        "methods": [method.value for method in methods],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{destination.name}.tmp-{uuid4().hex}"
    staging.mkdir()
    try:
        (staging / "analysis_index.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(staging, destination)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return destination / "analysis_index.json"


def read_analysis_index(source: Path) -> dict[str, object]:
    """Read and minimally validate a latest-analysis index."""
    path = source / "analysis_index.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"dataset_id", "dataset_path", "dataset_checksum", "config_path", "methods"}
    if not isinstance(payload, dict) or not required <= payload.keys():
        raise ValueError("Analysis index is malformed")
    return payload
