"""Versioned API contract, persistence, and artifact integration tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from graphtrust.api.app import create_app
from graphtrust.data.io import write_dataset
from graphtrust.experiments.registry import ExperimentUnit
from graphtrust.experiments.runner import run_experiment_unit
from graphtrust.schemas.findings import AnalysisMethod
from graphtrust.schemas.manifests import DatasetVariant
from graphtrust.settings import load_project_config
from tests.integration.test_dataset_io import small_bundle


def api_fixture(tmp_path: Path) -> tuple[TestClient, str, Path, Path]:
    data_root = tmp_path / "data"
    dataset_path = data_root / "saas_scaleup" / "small" / "104729" / "injected_low"
    written = write_dataset(small_bundle(), dataset_path)
    artifact_root = tmp_path / "artifacts"
    database = artifact_root / "api.duckdb"
    app = create_app(
        data_root=data_root,
        artifact_root=artifact_root,
        database_path=database,
    )
    return TestClient(app), written.manifest.dataset_id, artifact_root, database


def test_analysis_exploration_and_restart_persistence(tmp_path: Path) -> None:
    client, dataset_id, artifact_root, database = api_fixture(tmp_path)
    assert client.get("/api/v1/health").json()["status"] == "ok"
    datasets = client.get("/api/v1/datasets").json()
    assert datasets["total"] == 1
    assert datasets["items"][0]["dataset_id"] == dataset_id

    response = client.post(
        "/api/v1/analyses",
        json={"dataset_id": dataset_id, "methods": ["direct", "graphtrust"]},
    )
    assert response.status_code == 202, response.text
    analysis_id = response.json()["analysis_id"]
    job = client.get(f"/api/v1/analyses/{analysis_id}").json()
    assert job["status"] == "succeeded"
    summary = client.get(f"/api/v1/analyses/{analysis_id}/summary").json()
    assert summary["effective_edges"] == 1
    identities = client.get(
        f"/api/v1/analyses/{analysis_id}/identities",
        params={"search": "Engineer", "minimum_ztri": 0},
    ).json()
    assert identities["total"] == 2
    identity = client.get(f"/api/v1/analyses/{analysis_id}/identities/human:1").json()
    assert identity["top_paths"]
    paths = client.get(f"/api/v1/analyses/{analysis_id}/paths").json()
    path_id = paths["items"][0]["finding_id"]
    assert client.get(f"/api/v1/analyses/{analysis_id}/paths/{path_id}").status_code == 200

    counterfactual = client.post(
        f"/api/v1/analyses/{analysis_id}/counterfactual",
        json={"removed_edge_ids": ["edge:1"]},
    )
    assert counterfactual.status_code == 200, counterfactual.text
    assert counterfactual.json()["all_declared_pairs_blocked"] is True

    restarted = TestClient(
        create_app(
            data_root=tmp_path / "data",
            artifact_root=artifact_root,
            database_path=database,
        )
    )
    assert restarted.get(f"/api/v1/analyses/{analysis_id}").json()["status"] == "succeeded"
    assert restarted.get(f"/api/v1/analyses/{analysis_id}/summary").status_code == 200


def test_remediation_experiment_artifacts_and_explicit_errors(tmp_path: Path) -> None:
    client, dataset_id, artifact_root, _ = api_fixture(tmp_path)
    created = client.post(
        "/api/v1/analyses",
        json={"dataset_id": dataset_id, "methods": ["graphtrust"]},
    )
    analysis_id = created.json()["analysis_id"]
    remediation = client.post(
        f"/api/v1/analyses/{analysis_id}/remediations",
        json={"solvers": ["degree_greedy"], "targets": [0.8]},
    )
    assert remediation.status_code == 200, remediation.text
    plan = remediation.json()["items"][0]
    assert plan["caveats"][0].startswith("Recommendation only")
    assert (
        client.get(f"/api/v1/analyses/{analysis_id}/remediations/{plan['plan_id']}").status_code
        == 200
    )

    dataset_path = Path(client.get(f"/api/v1/datasets/{dataset_id}").json()["path"])
    unit = ExperimentUnit(
        dataset_path=dataset_path,
        dataset_id=dataset_id,
        profile="saas_scaleup",
        scale="small",
        seed=104729,
        variant=DatasetVariant.INJECTED_LOW,
        method=AnalysisMethod.DIRECT,
    )
    outcome = run_experiment_unit(
        unit,
        load_project_config(),
        output_root=artifact_root / "manifests",
    )
    experiments = client.get("/api/v1/experiments").json()
    assert experiments["items"][0]["run_id"] == outcome.run_id
    assert client.get(f"/api/v1/experiments/{outcome.run_id}/metrics").status_code == 200
    artifacts = client.get(f"/api/v1/experiments/{outcome.run_id}/artifacts").json()
    assert len(artifacts["artifacts"]) == 13

    missing = client.get("/api/v1/analyses/not-real")
    assert missing.status_code == 404
    assert missing.json() == {
        "error": {
            "code": "analysis_not_found",
            "message": "Analysis not-real was not found",
        }
    }
    invalid = client.get("/api/v1/datasets", params={"page_size": 1000})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"


def test_openapi_declares_every_required_route(tmp_path: Path) -> None:
    client, _, _, _ = api_fixture(tmp_path)
    routes = set(client.get("/openapi.json").json()["paths"])
    required = {
        "/api/v1/health",
        "/api/v1/datasets",
        "/api/v1/datasets/{dataset_id}",
        "/api/v1/analyses",
        "/api/v1/analyses/{analysis_id}",
        "/api/v1/analyses/{analysis_id}/summary",
        "/api/v1/analyses/{analysis_id}/identities",
        "/api/v1/analyses/{analysis_id}/identities/{node_id}",
        "/api/v1/analyses/{analysis_id}/paths",
        "/api/v1/analyses/{analysis_id}/paths/{path_id}",
        "/api/v1/analyses/{analysis_id}/remediations",
        "/api/v1/analyses/{analysis_id}/remediations/{plan_id}",
        "/api/v1/analyses/{analysis_id}/counterfactual",
        "/api/v1/experiments",
        "/api/v1/experiments/{run_id}/metrics",
        "/api/v1/experiments/{run_id}/artifacts",
    }
    assert required <= routes
