"""Small durable DuckDB repository for API job and plan state."""

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class ApiRepository:
    """Persist service state without coupling canonical graph data to DuckDB."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.path))

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    analysis_id VARCHAR PRIMARY KEY,
                    dataset_id VARCHAR NOT NULL,
                    dataset_path VARCHAR NOT NULL,
                    methods_json VARCHAR NOT NULL,
                    status VARCHAR NOT NULL,
                    created_at VARCHAR NOT NULL,
                    started_at VARCHAR,
                    completed_at VARCHAR,
                    error VARCHAR,
                    result_json VARCHAR
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS remediations (
                    plan_id VARCHAR PRIMARY KEY,
                    analysis_id VARCHAR NOT NULL,
                    payload_json VARCHAR NOT NULL,
                    created_at VARCHAR NOT NULL
                )
                """
            )

    def create_analysis(
        self,
        analysis_id: str,
        dataset_id: str,
        dataset_path: Path,
        methods: tuple[str, ...],
    ) -> dict[str, Any]:
        created_at = _utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO analyses VALUES (?, ?, ?, ?, 'queued', ?, NULL, NULL, NULL, NULL)",
                [analysis_id, dataset_id, str(dataset_path), json.dumps(methods), created_at],
            )
        value = self.get_analysis(analysis_id)
        assert value is not None
        return value

    def mark_running(self, analysis_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE analyses SET status = 'running', started_at = ? WHERE analysis_id = ?",
                [_utc_now(), analysis_id],
            )

    def mark_succeeded(self, analysis_id: str, result: dict[str, Any]) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """UPDATE analyses SET status = 'succeeded', completed_at = ?, result_json = ?,
                   error = NULL WHERE analysis_id = ?""",
                [_utc_now(), json.dumps(result, sort_keys=True), analysis_id],
            )

    def mark_failed(self, analysis_id: str, error: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """UPDATE analyses SET status = 'failed', completed_at = ?, error = ?
                WHERE analysis_id = ?""",
                [_utc_now(), error[:4_000], analysis_id],
            )

    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM analyses WHERE analysis_id = ?", [analysis_id]
            ).fetchone()
            columns = [column[0] for column in connection.description]
        if row is None:
            return None
        value = dict(zip(columns, row, strict=True))
        value["methods"] = tuple(json.loads(value.pop("methods_json")))
        result_json = value.pop("result_json")
        value["result"] = json.loads(result_json) if result_json else None
        return value

    def save_plan(self, analysis_id: str, plan_id: str, payload: dict[str, Any]) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO remediations VALUES (?, ?, ?, ?)",
                [plan_id, analysis_id, json.dumps(payload, sort_keys=True), _utc_now()],
            )

    def get_plan(self, analysis_id: str, plan_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM remediations WHERE analysis_id = ? AND plan_id = ?",
                [analysis_id, plan_id],
            ).fetchone()
        return json.loads(row[0]) if row else None
