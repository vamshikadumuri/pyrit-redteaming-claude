"""Run management routes — /runs and /runs/{run_id}/..."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.responses import HTMLResponse, StreamingResponse

from agentic_redteam.catalog.loader import Catalog
from agentic_redteam.records import RunRequest, RunSummary
from agentic_redteam.reports.aggregation import build_report
from agentic_redteam.store import Store
from agentic_redteam.web import presenters
from agentic_redteam.web.deps import get_catalog, get_manager, get_store
from agentic_redteam.web.manager import RunManager
from agentic_redteam.web.render import render
from agentic_redteam.web.utils import _build_run_request, _make_sse_generator

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("")
async def create_run(
    request: Request,
    store: Annotated[Store, Depends(get_store)],
    catalog: Annotated[Catalog, Depends(get_catalog)],
    manager: Annotated[RunManager, Depends(get_manager)],
) -> RedirectResponse:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
    else:
        form = await request.form()
        data = {}
        for k in form:
            vals = form.getlist(k)
            data[k] = vals if k in ("plugin_ids", "strategy_ids") or len(vals) > 1 else vals[0]

    run_id, req = _build_run_request(data, catalog)
    manager.start(req)
    _log.info("Run %s created by %s", run_id, req.requested_by)
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@router.get("")
async def run_list(
    request: Request,
    store: Annotated[Store, Depends(get_store)],
) -> HTMLResponse:
    rows = presenters.run_list_view(await store.list_runs())
    html = render("runs.html", title="Runs", rows=rows, request=request)
    return HTMLResponse(html)


@router.get("/{run_id}")
async def run_detail(
    run_id: str,
    request: Request,
    store: Annotated[Store, Depends(get_store)],
) -> HTMLResponse:
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
    return HTMLResponse(html)


@router.post("/{run_id}/stop")
async def stop_run(
    run_id: str,
    manager: Annotated[RunManager, Depends(get_manager)],
) -> RedirectResponse:
    manager.stop(run_id)
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@router.post("/{run_id}/rerun")
async def rerun_run(
    run_id: str,
    store: Annotated[Store, Depends(get_store)],
    manager: Annotated[RunManager, Depends(get_manager)],
) -> RedirectResponse:
    row = await store.get_run(run_id)
    if not row or not row.get("request_json"):
        return JSONResponse({"error": "No request data stored for this run"}, status_code=404)
    req = RunRequest.model_validate_json(row["request_json"])
    new_run_id = f"{run_id[:20]}_re_{uuid4().hex[:6]}"
    req.config.run_id = new_run_id
    manager.start(req)
    _log.info("Re-run %s created from %s", new_run_id, run_id)
    return RedirectResponse(f"/runs/{new_run_id}", status_code=303)


@router.get("/{run_id}/events")
async def run_events(
    run_id: str,
    request: Request,
    store: Annotated[Store, Depends(get_store)],
    manager: Annotated[RunManager, Depends(get_manager)],
) -> StreamingResponse:
    generate = _make_sse_generator(run_id, request, store, manager)
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/{run_id}/report")
async def run_report(
    run_id: str,
    request: Request,
    store: Annotated[Store, Depends(get_store)],
) -> HTMLResponse:
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
    return HTMLResponse(html)


@router.get("/{run_id}/report.json")
async def run_report_json(
    run_id: str,
    store: Annotated[Store, Depends(get_store)],
) -> JSONResponse:
    records = await store.get_executions(run_id)
    return JSONResponse(build_report(records))
