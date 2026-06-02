"""FastAPI web application (spec §13/§16). Container-only module — requires
fastapi, starlette, uvicorn in the image. Never imported by laptop tests."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import StreamingResponse

from agentic_redteam.catalog.loader import load_catalog
from agentic_redteam.config import ModelConfig
from agentic_redteam.engine.plan import RunConfig
from agentic_redteam.engine.profile import AppProfile
from agentic_redteam.records import RunRequest, RunSummary
from agentic_redteam.reports.aggregation import build_report
from agentic_redteam.store import Store
from agentic_redteam.web import demo, live, presenters
from agentic_redteam.web.manager import RunManager
from agentic_redteam.web.render import render

_STATIC = Path(__file__).resolve().parent / "static"
_FINAL = {"completed", "stopped", "failed"}


def _csv(v: str) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def _model(form, prefix: str, *, optional: bool = False) -> ModelConfig | None:
    endpoint = form.get(f"{prefix}_endpoint", "")
    if optional and not endpoint:
        return None
    temp_str = form.get(f"{prefix}_temperature", "")
    return ModelConfig(
        endpoint=endpoint,
        model_name=form.get(f"{prefix}_model", ""),
        api_key_env=form.get(f"{prefix}_api_key_env", ""),
        temperature=float(temp_str) if temp_str else None,
    )


def _sse(d: dict) -> str:
    return f"data: {json.dumps(d)}\n\n"


def create_app(*, store_path: str = ":memory:") -> FastAPI:
    app = FastAPI()
    catalog = load_catalog()
    store = Store(store_path)
    if os.environ.get("DEMO_MODE") == "1":
        exec_factory, llm_factory = demo.demo_executor_factory, demo.demo_llm_factory
    else:
        exec_factory, llm_factory = live.real_executor_factory, live.real_llm_factory
    manager = RunManager(
        catalog,
        store,
        executor_factory=exec_factory,
        llm_factory=llm_factory,
    )

    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

    @app.get("/")
    async def wizard_route(request: Request):
        from agentic_redteam.web.presenters import wizard_view
        html = render("wizard.html", title="New Run", wizard=wizard_view(catalog), request=request)
        from starlette.responses import HTMLResponse
        return HTMLResponse(html)

    def _build_run_request(data: dict) -> tuple[str, RunRequest]:
        """Build a RunRequest from a flat dict (form or JSON body)."""
        raw_id = (data.get("run_id") or "").strip()
        run_id = raw_id if raw_id else f"run_{uuid4().hex[:8]}"

        preset_id = (data.get("preset") or "").strip()
        if preset_id:
            preset = catalog.presets[preset_id]
            plugin_ids = list(preset.plugins)
            strategy_ids = list(preset.recommended_strategies) or ["basic"]
        else:
            raw_plugins = data.get("plugin_ids", [])
            plugin_ids = raw_plugins if isinstance(raw_plugins, list) else _csv(raw_plugins)
            raw_strats = data.get("strategy_ids", [])
            strategy_ids = (raw_strats if isinstance(raw_strats, list) else _csv(raw_strats)) or ["basic"]

        profile = AppProfile(
            purpose=data.get("purpose", ""),
            tools=_csv(data.get("tools", "")) if isinstance(data.get("tools", ""), str) else (data.get("tools") or []),
            roles=_csv(data.get("roles", "")) if isinstance(data.get("roles", ""), str) else (data.get("roles") or []),
            data_channels=_csv(data.get("data_channels", "")) if isinstance(data.get("data_channels", ""), str) else (data.get("data_channels") or []),
            entities=_csv(data.get("entities", "")) if isinstance(data.get("entities", ""), str) else (data.get("entities") or []),
        )

        n_str = data.get("n", "5")
        concurrency_str = data.get("concurrency", "4")
        n = int(n_str) if n_str else 5
        concurrency = int(concurrency_str) if concurrency_str else 4

        config = RunConfig(
            run_id=run_id,
            plugin_ids=plugin_ids,
            strategy_ids=strategy_ids,
            profile=profile,
            n=n,
            policy_text=data.get("policy_text", ""),
        )

        target = _model(data, "target")
        judge = _model(data, "judge")
        adversarial = _model(data, "adversarial", optional=True)

        req = RunRequest(
            config=config,
            target=target,
            judge=judge,
            adversarial=adversarial,
            concurrency=concurrency,
            requested_by=data.get("requested_by", ""),
        )
        return run_id, req

    @app.post("/runs")
    async def create_run(request: Request):
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)

        run_id, req = _build_run_request(data)
        manager.start(req)
        return RedirectResponse(f"/runs/{run_id}", status_code=303)

    @app.get("/runs/{run_id}")
    async def run_detail(run_id: str, request: Request):
        row = store.get_run(run_id)
        if row and row.get("summary_json") and row["summary_json"] != "{}":
            try:
                summary = RunSummary.model_validate_json(row["summary_json"])
            except Exception:
                summary = RunSummary(run_id=run_id, status=row.get("status", "pending"))
        else:
            summary = RunSummary(run_id=run_id, status=(row["status"] if row else "pending"))
        records = store.get_executions(run_id)
        ctx = presenters.report_context(summary, records)
        html = render("live.html", title=f"Run {run_id}", run_id=run_id, ctx=ctx, request=request)
        from starlette.responses import HTMLResponse
        return HTMLResponse(html)

    @app.get("/runs/{run_id}/events")
    async def run_events(run_id: str, request: Request):
        q = manager.bus.subscribe()

        async def generate():
            # Replay already-completed executions from the store
            for rec in store.get_executions(run_id):
                d = {
                    "kind": "execution_done",
                    "run_id": rec.run_id,
                    "plugin_id": rec.plugin_id,
                    "strategy_id": rec.strategy_id,
                    "objective_id": rec.objective_id,
                    "status": rec.status,
                }
                yield _sse(d)

            # Check if run is already final
            row = store.get_run(run_id)
            if row and row.get("status") in _FINAL:
                yield _sse({"kind": "run_finished", "run_id": run_id, "status": row["status"]})
                return

            # Stream live events
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # Skip events for other runs
                if event.run_id != run_id:
                    continue

                d = event.model_dump()
                yield _sse(d)

                if event.kind == "run_finished":
                    break

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.post("/runs/{run_id}/stop")
    async def stop_run(run_id: str):
        manager.stop(run_id)
        return RedirectResponse(f"/runs/{run_id}", status_code=303)

    @app.get("/runs/{run_id}/report.json")
    async def run_report_json(run_id: str):
        records = store.get_executions(run_id)
        return JSONResponse(build_report(records))

    @app.get("/runs/{run_id}/report")
    async def run_report(run_id: str, request: Request):
        row = store.get_run(run_id)
        if row and row.get("summary_json") and row["summary_json"] != "{}":
            try:
                summary = RunSummary.model_validate_json(row["summary_json"])
            except Exception:
                summary = RunSummary(run_id=run_id, status=row.get("status", "pending"))
        else:
            summary = RunSummary(run_id=run_id, status=(row["status"] if row else "unknown"))
        records = store.get_executions(run_id)
        ctx = presenters.report_context(summary, records)
        html = render("report.html", title=f"Report — {run_id}", ctx=ctx, request=request)
        from starlette.responses import HTMLResponse
        return HTMLResponse(html)

    @app.get("/runs")
    async def run_list(request: Request):
        rows = presenters.run_list_view(store.list_runs())
        html = render("runs.html", title="Runs", rows=rows, request=request)
        from starlette.responses import HTMLResponse
        return HTMLResponse(html)

    return app
