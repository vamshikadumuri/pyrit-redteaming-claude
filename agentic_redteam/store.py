# agentic_redteam/store.py
"""SQLite app store (spec §12): runs, per-execution summaries, and the audit log
(the authorization record per run). Uses aiosqlite — no PyRIT. PyRIT memory
(DuckDB) holds conversations/scores; this store is the app-side index for the run
list, live-view replay, and audit trail. JSON columns keep snapshots diffable."""

from __future__ import annotations

import logging
import time

import aiosqlite

from agentic_redteam.records import ExecutionRecord, RunRequest, RunSummary

_log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    status          TEXT NOT NULL,
    requested_by    TEXT NOT NULL DEFAULT '',
    target_endpoint TEXT NOT NULL DEFAULT '',
    config_json     TEXT NOT NULL,
    summary_json    TEXT NOT NULL DEFAULT '{}',
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS executions (
    run_id          TEXT NOT NULL,
    plugin_id       TEXT NOT NULL,
    strategy_id     TEXT NOT NULL,
    objective_id    TEXT NOT NULL,
    status          TEXT NOT NULL,
    record_json     TEXT NOT NULL,
    PRIMARY KEY (run_id, plugin_id, strategy_id, objective_id)
);
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    requested_by    TEXT NOT NULL,
    target_endpoint TEXT NOT NULL,
    objective_count INTEGER NOT NULL,
    created_at      REAL NOT NULL,
    detail          TEXT NOT NULL DEFAULT ''
);
"""


class Store:
    """The application's SQLite store. Default :memory: for hermetic tests; pass a
    file path for the web app / notebook so runs persist and the history survives."""

    def __init__(self, path: str = ":memory:"):
        self._path = path
        self._db: aiosqlite.Connection | None = None

    async def _open(self) -> None:
        if self._db is not None:
            return
        self._db = await aiosqlite.connect(self._path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def _ensure_open(self) -> None:
        if self._db is None:
            await self._open()

    @property
    def _conn(self) -> aiosqlite.Connection:
        assert self._db is not None
        return self._db

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()

    # ---- runs ----
    async def create_run(self, request: RunRequest) -> None:
        await self._ensure_open()
        now = time.time()
        await self._conn.execute(
            "INSERT INTO runs(run_id,status,requested_by,target_endpoint,config_json,"
            "summary_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                request.config.run_id,
                "pending",
                request.requested_by,
                request.target.endpoint,
                request.config.model_dump_json(),
                "{}",
                now,
                now,
            ),
        )
        await self._conn.commit()

    async def set_status(self, run_id: str, status: str) -> None:
        await self._ensure_open()
        await self._conn.execute(
            "UPDATE runs SET status=?, updated_at=? WHERE run_id=?", (status, time.time(), run_id)
        )
        await self._conn.commit()

    async def save_summary(self, summary: RunSummary) -> None:
        await self._ensure_open()
        await self._conn.execute(
            "UPDATE runs SET status=?, summary_json=?, updated_at=? WHERE run_id=?",
            (summary.status, summary.model_dump_json(), time.time(), summary.run_id),
        )
        await self._conn.commit()

    async def get_run(self, run_id: str) -> dict | None:
        await self._ensure_open()
        async with self._conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            _log.debug("get_run(%r) returned None — run not found in store", run_id)
        return dict(row) if row else None

    async def list_runs(self) -> list[dict]:
        await self._ensure_open()
        async with self._conn.execute("SELECT * FROM runs ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    # ---- executions ----
    async def save_execution(self, record: ExecutionRecord) -> None:
        await self._ensure_open()
        await self._conn.execute(
            "INSERT OR REPLACE INTO executions(run_id,plugin_id,strategy_id,objective_id,"
            "status,record_json) VALUES(?,?,?,?,?,?)",
            (
                record.run_id,
                record.plugin_id,
                record.strategy_id,
                record.objective_id,
                record.status,
                record.model_dump_json(),
            ),
        )
        await self._conn.commit()

    async def get_executions(self, run_id: str) -> list[ExecutionRecord]:
        await self._ensure_open()
        async with self._conn.execute(
            "SELECT record_json FROM executions WHERE run_id=? ORDER BY plugin_id,strategy_id",
            (run_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [ExecutionRecord.model_validate_json(r["record_json"]) for r in rows]

    # ---- audit ----
    async def add_audit(
        self,
        *,
        run_id: str,
        requested_by: str,
        target_endpoint: str,
        objective_count: int,
        detail: str = "",
    ) -> None:
        await self._ensure_open()
        await self._conn.execute(
            "INSERT INTO audit_log(run_id,requested_by,target_endpoint,objective_count,"
            "created_at,detail) VALUES(?,?,?,?,?,?)",
            (run_id, requested_by, target_endpoint, objective_count, time.time(), detail),
        )
        await self._conn.commit()

    async def get_audit(self, run_id: str) -> list[dict]:
        await self._ensure_open()
        async with self._conn.execute(
            "SELECT * FROM audit_log WHERE run_id=? ORDER BY created_at", (run_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
