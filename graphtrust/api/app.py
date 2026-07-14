"""FastAPI application factory and complete `/api/v1` route contract."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from graphtrust import __version__
from graphtrust.api.repository import ApiRepository
from graphtrust.api.schemas import (
    AnalysisCreate,
    AnalysisJob,
    ArtifactDescriptor,
    ArtifactPage,
    CounterfactualRequest,
    DatasetPage,
    DatasetSummary,
    ErrorResponse,
    HealthResponse,
    RemediationCreate,
)
from graphtrust.api.services import counterfactual, execute_analysis_job, remediate
from graphtrust.data.checksums import sha256_file
from graphtrust.experiments.runner import RUN_FILES, verify_run_directory
from graphtrust.schemas.manifests import DatasetManifest, RunManifest
from graphtrust.settings import EnvironmentSettings, load_project_config

Page = Annotated[int, Query(ge=1, le=1_000_000)]
PageSize = Annotated[int, Query(ge=1, le=200)]


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _datasets(data_root: Path) -> dict[str, DatasetSummary]:
    catalog: dict[str, DatasetSummary] = {}
    if not data_root.exists():
        return catalog
    for manifest_path in sorted(data_root.rglob("manifest.json")):
        try:
            manifest = DatasetManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            continue
        catalog[manifest.dataset_id] = DatasetSummary(
            dataset_id=manifest.dataset_id,
            profile=manifest.profile,
            scale=manifest.scale.value,
            variant=manifest.variant.value,
            seed=manifest.generator_seed,
            path=str(manifest_path.parent),
            counts=manifest.realized_counts,
            warnings=manifest.warnings,
        )
    return catalog


def _analysis_job(row: dict[str, Any]) -> AnalysisJob:
    return AnalysisJob(
        analysis_id=str(row["analysis_id"]),
        dataset_id=str(row["dataset_id"]),
        methods=tuple(row["methods"]),
        status=str(row["status"]),
        created_at=row["created_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        error=row["error"],
    )


def _require_analysis(repository: ApiRepository, analysis_id: str) -> dict[str, Any]:
    row = repository.get_analysis(analysis_id)
    if row is None:
        raise _error(404, "analysis_not_found", f"Analysis {analysis_id} was not found")
    return row


def _require_result(row: dict[str, Any]) -> dict[str, Any]:
    if row["status"] != "succeeded" or row["result"] is None:
        raise _error(409, "analysis_not_ready", f"Analysis status is {row['status']}")
    result = row["result"]
    if not isinstance(result, dict):
        raise _error(500, "invalid_analysis_state", "Persisted analysis result is invalid")
    return result


def create_app(
    *,
    data_root: Path | None = None,
    artifact_root: Path | None = None,
    database_path: Path | None = None,
) -> FastAPI:
    """Construct an isolated, testable service instance."""
    environment = EnvironmentSettings()
    resolved_data = data_root or environment.data_root
    resolved_artifacts = artifact_root or environment.artifact_root
    resolved_database = database_path or environment.database_path
    repository = ApiRepository(resolved_database)
    config = load_project_config()
    app = FastAPI(
        title="GraphTrust API",
        version=__version__,
        description="Versioned investigation API over immutable GraphTrust analyses.",
    )
    app.state.repository = repository
    app.state.data_root = resolved_data
    app.state.artifact_root = resolved_artifacts

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, error: HTTPException) -> JSONResponse:
        detail = error.detail
        if isinstance(detail, dict) and "code" in detail:
            body = {"error": detail}
        else:
            body = {"error": {"code": "http_error", "message": str(detail)}}
        return JSONResponse(status_code=error.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "details": jsonable_encoder(error.errors()),
                }
            },
        )

    error_responses: dict[int | str, dict[str, Any]] = {
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    }

    @app.get("/api/v1/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__, database=str(resolved_database))

    @app.get("/api/v1/datasets", response_model=DatasetPage)
    async def datasets(page: Page = 1, page_size: PageSize = 50) -> DatasetPage:
        catalog = await run_in_threadpool(_datasets, resolved_data)
        values = tuple(catalog.values())
        start = (page - 1) * page_size
        return DatasetPage(
            items=values[start : start + page_size],
            total=len(values),
            page=page,
            page_size=page_size,
        )

    @app.get(
        "/api/v1/datasets/{dataset_id}", response_model=DatasetSummary, responses=error_responses
    )
    async def dataset_detail(dataset_id: str) -> DatasetSummary:
        catalog = await run_in_threadpool(_datasets, resolved_data)
        dataset = catalog.get(dataset_id)
        if dataset is None:
            raise _error(404, "dataset_not_found", f"Dataset {dataset_id} was not found")
        return dataset

    @app.post(
        "/api/v1/analyses", response_model=AnalysisJob, status_code=202, responses=error_responses
    )
    async def create_analysis(request: AnalysisCreate, background: BackgroundTasks) -> AnalysisJob:
        if len(set(request.methods)) != len(request.methods):
            raise _error(422, "duplicate_methods", "Analysis methods must be unique")
        catalog = await run_in_threadpool(_datasets, resolved_data)
        dataset = catalog.get(request.dataset_id)
        if dataset is None:
            raise _error(404, "dataset_not_found", f"Dataset {request.dataset_id} was not found")
        created = datetime.now(UTC).isoformat()
        material = "\0".join(
            (request.dataset_id, *(method.value for method in request.methods), created)
        )
        analysis_id = "analysis-" + hashlib.sha256(material.encode()).hexdigest()[:24]
        row = repository.create_analysis(
            analysis_id,
            request.dataset_id,
            Path(dataset.path),
            tuple(method.value for method in request.methods),
        )
        background.add_task(
            execute_analysis_job,
            repository,
            analysis_id,
            Path(dataset.path),
            request.methods,
            config,
        )
        return _analysis_job(row)

    @app.get(
        "/api/v1/analyses/{analysis_id}", response_model=AnalysisJob, responses=error_responses
    )
    async def analysis_detail(analysis_id: str) -> AnalysisJob:
        return _analysis_job(_require_analysis(repository, analysis_id))

    @app.get("/api/v1/analyses/{analysis_id}/summary", responses=error_responses)
    async def analysis_summary(analysis_id: str) -> dict[str, Any]:
        return dict(_require_result(_require_analysis(repository, analysis_id))["summary"])

    @app.get("/api/v1/analyses/{analysis_id}/identities", responses=error_responses)
    async def identities(
        analysis_id: str,
        page: Page = 1,
        page_size: PageSize = 50,
        search: Annotated[str | None, Query(max_length=200)] = None,
        node_type: Annotated[str | None, Query(max_length=80)] = None,
        provider: Annotated[str | None, Query(max_length=80)] = None,
        department: Annotated[str | None, Query(max_length=120)] = None,
        minimum_ztri: Annotated[float, Query(ge=0, le=100)] = 0,
        maximum_ztri: Annotated[float, Query(ge=0, le=100)] = 100,
    ) -> dict[str, Any]:
        rows = list(_require_result(_require_analysis(repository, analysis_id))["identities"])
        query = (search or "").casefold()
        filtered = [
            row
            for row in rows
            if minimum_ztri <= float(row["ztri"]) <= maximum_ztri
            and (
                not query
                or query in str(row["display_name"]).casefold()
                or query in str(row["node_id"]).casefold()
            )
            and (node_type is None or row["node_type"] == node_type)
            and (provider is None or row["provider"] == provider)
            and (department is None or row["department"] == department)
        ]
        start = (page - 1) * page_size
        return {
            "items": filtered[start : start + page_size],
            "total": len(filtered),
            "page": page,
            "page_size": page_size,
        }

    @app.get("/api/v1/analyses/{analysis_id}/identities/{node_id}", responses=error_responses)
    async def identity_detail(analysis_id: str, node_id: str) -> dict[str, Any]:
        result = _require_result(_require_analysis(repository, analysis_id))
        matches = [row for row in result["identities"] if row["node_id"] == node_id]
        if not matches:
            raise _error(404, "identity_not_found", f"Identity {node_id} was not found")
        paths = [row for row in result["paths"] if row["source_identity_id"] == node_id]
        return {"scores": matches, "top_paths": paths[:20]}

    @app.get("/api/v1/analyses/{analysis_id}/paths", responses=error_responses)
    async def paths(
        analysis_id: str,
        page: Page = 1,
        page_size: PageSize = 50,
        source_id: Annotated[str | None, Query(max_length=300)] = None,
        target_id: Annotated[str | None, Query(max_length=300)] = None,
    ) -> dict[str, Any]:
        rows = list(_require_result(_require_analysis(repository, analysis_id))["paths"])
        filtered = [
            row
            for row in rows
            if (source_id is None or row["source_identity_id"] == source_id)
            and (target_id is None or row["target_asset_id"] == target_id)
        ]
        start = (page - 1) * page_size
        return {
            "items": filtered[start : start + page_size],
            "total": len(filtered),
            "page": page,
            "page_size": page_size,
        }

    @app.get("/api/v1/analyses/{analysis_id}/paths/{path_id}", responses=error_responses)
    async def path_detail(analysis_id: str, path_id: str) -> dict[str, Any]:
        rows = _require_result(_require_analysis(repository, analysis_id))["paths"]
        match = next((row for row in rows if row["finding_id"] == path_id), None)
        if match is None:
            raise _error(404, "path_not_found", f"Path {path_id} was not found")
        return dict(match)

    @app.post("/api/v1/analyses/{analysis_id}/remediations", responses=error_responses)
    async def create_remediations(analysis_id: str, request: RemediationCreate) -> dict[str, Any]:
        row = _require_analysis(repository, analysis_id)
        _require_result(row)
        if any(not 0 < target <= 1 for target in request.targets):
            raise _error(422, "invalid_target", "Targets must be in (0, 1]")
        plans = await run_in_threadpool(
            remediate,
            Path(row["dataset_path"]),
            config,
            request.solvers,
            request.targets,
        )
        for plan in plans:
            repository.save_plan(analysis_id, str(plan["plan_id"]), plan)
        return {"items": plans, "recommendation_only": True}

    @app.get("/api/v1/analyses/{analysis_id}/remediations/{plan_id}", responses=error_responses)
    async def remediation_detail(analysis_id: str, plan_id: str) -> dict[str, Any]:
        _require_analysis(repository, analysis_id)
        plan = repository.get_plan(analysis_id, plan_id)
        if plan is None:
            raise _error(404, "plan_not_found", f"Plan {plan_id} was not found")
        return plan

    @app.post("/api/v1/analyses/{analysis_id}/counterfactual", responses=error_responses)
    async def run_counterfactual(
        analysis_id: str, request: CounterfactualRequest
    ) -> dict[str, Any]:
        row = _require_analysis(repository, analysis_id)
        _require_result(row)
        try:
            return await run_in_threadpool(
                counterfactual,
                Path(row["dataset_path"]),
                config,
                request.removed_edge_ids,
            )
        except ValueError as error:
            raise _error(422, "invalid_edge_selection", str(error)) from error

    def experiment_directory(run_id: str) -> Path:
        root = resolved_artifacts / "manifests"
        match = root / run_id
        if match.parent != root or not match.is_dir():
            raise _error(404, "experiment_not_found", f"Experiment {run_id} was not found")
        valid, failures = verify_run_directory(match)
        if not valid:
            raise _error(409, "experiment_corrupt", ", ".join(failures))
        return match

    @app.get("/api/v1/experiments")
    async def experiments(page: Page = 1, page_size: PageSize = 50) -> dict[str, Any]:
        root = resolved_artifacts / "manifests"
        rows: list[dict[str, Any]] = []
        if root.is_dir():
            for directory in sorted(
                path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")
            ):
                valid, _ = verify_run_directory(directory)
                if valid:
                    manifest = RunManifest.model_validate_json(
                        (directory / "run_manifest.json").read_text(encoding="utf-8")
                    )
                    rows.append(manifest.model_dump(mode="json"))
        start = (page - 1) * page_size
        return {
            "items": rows[start : start + page_size],
            "total": len(rows),
            "page": page,
            "page_size": page_size,
        }

    @app.get("/api/v1/experiments/{run_id}/metrics", responses=error_responses)
    async def experiment_metrics(run_id: str) -> dict[str, Any]:
        return dict(
            json.loads((experiment_directory(run_id) / "metrics.json").read_text(encoding="utf-8"))
        )

    @app.get(
        "/api/v1/experiments/{run_id}/artifacts",
        response_model=ArtifactPage,
        responses=error_responses,
    )
    async def experiment_artifacts(run_id: str) -> ArtifactPage:
        directory = experiment_directory(run_id)
        artifacts = tuple(
            ArtifactDescriptor(
                name=name,
                size_bytes=(directory / name).stat().st_size,
                sha256=sha256_file(directory / name),
            )
            for name in (*RUN_FILES, "checksums.sha256")
        )
        return ArtifactPage(run_id=run_id, artifacts=artifacts)

    return app


app = create_app()
