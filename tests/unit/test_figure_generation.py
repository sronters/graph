"""Regression coverage for evidence-backed publication figure helpers."""

import json
from pathlib import Path

from scripts.generate_figures import remediation_figure


def test_remediation_figure_serializes_nested_plan_fields(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    plan_directory = artifact_root / "remediation" / "degree"
    plan_directory.mkdir(parents=True)
    (plan_directory / "remediation_plans.json").write_text(
        json.dumps(
            [
                {
                    "plan_id": "plan:test",
                    "solver": "degree_greedy",
                    "target_fraction": 0.8,
                    "modeled_cost": 2.0,
                    "residual_exposure": 0.2,
                    "removed_edge_ids": ["edge:a", "edge:b"],
                    "affected_departments": ["Engineering"],
                }
            ]
        ),
        encoding="utf-8",
    )
    figures = artifact_root / "paper" / "figures"
    tables = artifact_root / "paper" / "tables"
    figures.mkdir(parents=True)
    tables.mkdir(parents=True)

    remediation_figure(artifact_root, figures, tables)

    csv_text = (tables / "04_remediation_results.csv").read_text(encoding="utf-8")
    assert '"[""edge:a"",""edge:b""]"' in csv_text
    assert (figures / "06_remediation_frontier.svg").is_file()
