"""FastAPI web application (spec §13/§16). Container-only module — requires
fastapi, starlette, uvicorn in the image. Never imported by laptop tests."""

from __future__ import annotations

import asyncio
import json
import logging
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
from agentic_redteam.web import live, presenters
from agentic_redteam.web.manager import RunManager
from agentic_redteam.web.render import render

_log = logging.getLogger(__name__)

_STATIC = Path(__file__).resolve().parent / "static"
_FINAL = {"completed", "stopped", "failed"}

# ── Step fields per wizard step (used to exclude them from hidden inputs) ──
_STEP_FIELDS: dict[int, set[str]] = {
    1: {"target_endpoint", "target_model", "target_api_key_env"},
    2: {"preset", "plugin_ids", "strategy_ids", "scope_mode"},
    3: {"adversarial_endpoint", "adversarial_model", "adversarial_api_key_env"},
    4: {"judge_endpoint", "judge_model", "judge_api_key_env"},
    5: {"purpose", "tools", "roles", "data_channels", "entities"},
    6: {"n", "concurrency", "requested_by", "policy_text"},
}
_ALWAYS_EXCLUDE = {"completed_steps", "scope_mode"}


def _hidden_fields(data: dict, current_n: int) -> str:
    """Return hidden <input> elements for all accumulated data except current step's fields."""
    from markupsafe import Markup, escape

    exclude = _STEP_FIELDS.get(current_n, set()) | _ALWAYS_EXCLUDE
    parts = []
    for k, v in data.items():
        if k in exclude:
            continue
        values = v if isinstance(v, list) else [v]
        for val in values:
            parts.append(f'<input type="hidden" name="{escape(k)}" value="{escape(str(val))}">')
    return Markup("\n".join(parts))


def _wizard_ctx(n: int, data: dict, catalog, errors: dict | None = None) -> dict:
    from agentic_redteam.web.presenters import wizard_view

    return {
        "n": n,
        "data": data,
        "errors": errors or {},
        "wizard": wizard_view(catalog),
        "hidden": _hidden_fields(data, n),
        "completed_steps": data.get("completed_steps", ""),
    }


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


def _sse(event: str, html: str) -> str:
    # SSE format: event name + single-line data (strip internal newlines)
    payload = html.replace("\n", " ").replace("\r", "")
    return f"event: {event}\ndata: {payload}\n\n"


async def _parse_form(request: Request) -> dict:
    """Parse application/x-www-form-urlencoded without python-multipart."""
    from urllib.parse import parse_qs

    body = await request.body()
    raw = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    data: dict = {}
    for k, vals in raw.items():
        data[k] = vals if k in ("plugin_ids", "strategy_ids") or len(vals) > 1 else vals[0]
    return data


def create_app(
    *,
    store_path: str = ":memory:",
    exec_factory=None,
    llm_factory=None,
) -> FastAPI:
    from contextlib import asynccontextmanager

    catalog = load_catalog()
    store = Store(store_path)

    @asynccontextmanager
    async def _lifespan(application: FastAPI):
        await store._open()
        try:
            from pyrit.setup import IN_MEMORY, initialize_pyrit_async

            await initialize_pyrit_async(memory_db_type=IN_MEMORY)
        except ImportError:
            pass  # PyRIT not installed (laptop / test environment)
        _log.info("App startup complete (store=%s)", store_path)
        try:
            yield
        finally:
            _log.info("App shutdown")
            await store.close()

    app = FastAPI(lifespan=_lifespan)
    if exec_factory is None:
        exec_factory = live.real_executor_factory
    if llm_factory is None:
        llm_factory = live.real_llm_factory
    manager = RunManager(
        catalog,
        store,
        executor_factory=exec_factory,
        llm_factory=llm_factory,
    )

    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

    @app.get("/")
    async def wizard_route(request: Request):
        from starlette.responses import HTMLResponse

        html = render(
            "wizard.html", title="New Run", **_wizard_ctx(1, {}, catalog), request=request
        )
        return HTMLResponse(html)

    @app.get("/wizard/step/{n}")
    async def wizard_step_get(n: int, request: Request):
        from starlette.responses import HTMLResponse

        params: dict = dict(request.query_params)
        # Multi-value query params (plugin_ids, strategy_ids)
        for key in ("plugin_ids", "strategy_ids"):
            vals = request.query_params.getlist(key)
            if vals:
                params[key] = vals
        ctx = _wizard_ctx(n, params, catalog)
        return HTMLResponse(render(f"partials/wizard_step_{n}.html", **ctx))

    @app.post("/wizard/step/{n}")
    async def wizard_step_post(n: int, request: Request):
        """Re-render step n with form data (Back navigation / completed-step edit)."""
        from starlette.responses import HTMLResponse

        data = await _parse_form(request)
        ctx = _wizard_ctx(n, data, catalog)
        return HTMLResponse(render(f"partials/wizard_step_{n}.html", **ctx))

    @app.post("/wizard/step/{n}/next")
    async def wizard_step_next(n: int, request: Request):
        from starlette.responses import HTMLResponse

        data = await _parse_form(request)

        errors: dict[str, str] = {}
        if n == 1:
            if not data.get("target_endpoint", "").strip():
                errors["target_endpoint"] = "Endpoint is required"
            if not data.get("target_model", "").strip():
                errors["target_model"] = "Model name is required"
        elif n == 4:
            if not data.get("judge_endpoint", "").strip():
                errors["judge_endpoint"] = "Endpoint is required"
            if not data.get("judge_model", "").strip():
                errors["judge_model"] = "Model name is required"

        if errors:
            ctx = _wizard_ctx(n, data, catalog, errors)
            return HTMLResponse(render(f"partials/wizard_step_{n}.html", **ctx))

        # Mark step n complete, advance to n+1
        done = {int(x) for x in data.get("completed_steps", "").split(",") if x.strip().isdigit()}
        done.add(n)
        data["completed_steps"] = ",".join(str(x) for x in sorted(done))

        next_n = min(n + 1, 6)
        ctx = _wizard_ctx(next_n, data, catalog)
        return HTMLResponse(render(f"partials/wizard_step_{next_n}.html", **ctx))

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
            strategy_ids = (raw_strats if isinstance(raw_strats, list) else _csv(raw_strats)) or [
                "basic"
            ]

        profile = AppProfile(
            purpose=data.get("purpose", ""),
            tools=_csv(data.get("tools", ""))
            if isinstance(data.get("tools", ""), str)
            else (data.get("tools") or []),
            roles=_csv(data.get("roles", ""))
            if isinstance(data.get("roles", ""), str)
            else (data.get("roles") or []),
            data_channels=_csv(data.get("data_channels", ""))
            if isinstance(data.get("data_channels", ""), str)
            else (data.get("data_channels") or []),
            entities=_csv(data.get("entities", ""))
            if isinstance(data.get("entities", ""), str)
            else (data.get("entities") or []),
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
        assert target is not None
        judge = _model(data, "judge")
        assert judge is not None
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
            data = await _parse_form(request)

        run_id, req = _build_run_request(data)
        manager.start(req)
        _log.info("Run %s created by %s", run_id, req.requested_by)
        return RedirectResponse(f"/runs/{run_id}", status_code=303)

    @app.get("/runs/{run_id}")
    async def run_detail(run_id: str, request: Request):
        row = await store.get_run(run_id)
        if row and row.get("summary_json") and row["summary_json"] != "{}":
            try:
                summary = RunSummary.model_validate_json(row["summary_json"])
            except Exception:
                summary = RunSummary(run_id=run_id, status=row.get("status", "pending"))
        else:
            summary = RunSummary(run_id=run_id, status=(row["status"] if row else "pending"))
        records = await store.get_executions(run_id)
        ctx = presenters.report_context(summary, records)
        html = render("live.html", title=f"Run {run_id}", run_id=run_id, ctx=ctx, request=request)
        from starlette.responses import HTMLResponse

        return HTMLResponse(html)

    @app.get("/runs/{run_id}/events")
    async def run_events(run_id: str, request: Request):
        q, unsub = manager.bus.subscribe()

        async def generate():
            _log.info("SSE client connected for run %s", run_id)
            try:
                # Replay already-completed executions from the store
                for rec in await store.get_executions(run_id):
                    html = render(
                        "partials/feed_row.html",
                        plugin_id=rec.plugin_id,
                        strategy_id=rec.strategy_id,
                        status=rec.status,
                    )
                    yield _sse("execution_done", html)

                # Check if run is already final
                row = await store.get_run(run_id)
                if row and row.get("status") in _FINAL:
                    html = render("partials/run_finished.html", run_id=run_id, status=row["status"])
                    yield _sse("run_finished", html)
                    return

                # Stream live events
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(q.get(), timeout=1.0)
                    except TimeoutError:
                        continue

                    if event.run_id != run_id:
                        continue

                    if event.kind == "execution_done":
                        html = render(
                            "partials/feed_row.html",
                            plugin_id=event.plugin_id,
                            strategy_id=event.strategy_id,
                            status=event.status,
                        )
                        yield _sse("execution_done", html)
                    elif event.kind == "run_finished":
                        row = await store.get_run(run_id)
                        final_status = row["status"] if row else "completed"
                        html = render(
                            "partials/run_finished.html", run_id=run_id, status=final_status
                        )
                        yield _sse("run_finished", html)
                        break
                    else:
                        d = event.model_dump()
                        yield _sse(event.kind, json.dumps(d))
            finally:
                _log.info("SSE client disconnected for run %s", run_id)
                unsub()

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.post("/runs/{run_id}/stop")
    async def stop_run(run_id: str):
        manager.stop(run_id)
        return RedirectResponse(f"/runs/{run_id}", status_code=303)

    @app.get("/runs/{run_id}/report.json")
    async def run_report_json(run_id: str):
        records = await store.get_executions(run_id)
        return JSONResponse(build_report(records))

    @app.get("/runs/{run_id}/report")
    async def run_report(run_id: str, request: Request):
        row = await store.get_run(run_id)
        if row and row.get("summary_json") and row["summary_json"] != "{}":
            try:
                summary = RunSummary.model_validate_json(row["summary_json"])
            except Exception:
                summary = RunSummary(run_id=run_id, status=row.get("status", "pending"))
        else:
            summary = RunSummary(run_id=run_id, status=(row["status"] if row else "unknown"))
        records = await store.get_executions(run_id)
        ctx = presenters.report_context(summary, records)
        html = render("report.html", title=f"Report — {run_id}", ctx=ctx, request=request)
        from starlette.responses import HTMLResponse

        return HTMLResponse(html)

    @app.get("/runs")
    async def run_list(request: Request):
        rows = presenters.run_list_view(await store.list_runs())
        html = render("runs.html", title="Runs", rows=rows, request=request)
        from starlette.responses import HTMLResponse

        return HTMLResponse(html)

    return app
