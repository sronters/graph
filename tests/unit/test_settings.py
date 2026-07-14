"""Configuration loading tests."""

from pathlib import Path

import pytest

from graphtrust.settings import load_project_config, load_yaml


def test_default_configuration_matches_declared_contract() -> None:
    config = load_project_config(Path("configs/default.yaml"))
    assert config.analysis.maximum_depth == 8
    assert config.analysis.global_path_cap == 250_000
    assert config.condition_mode == "conservative"


def test_non_mapping_yaml_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a YAML mapping"):
        load_yaml(path)
