"""Wizard routes — GET / and /wizard/step/{n} variants."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from starlette.responses import HTMLResponse

from agentic_redteam.catalog.loader import Catalog
from agentic_redteam.web.deps import get_catalog
from agentic_redteam.web.render import render
from agentic_redteam.web.utils import _parse_form, _wizard_ctx

router = APIRouter(tags=["wizard"])


@router.get("/")
async def wizard_route(
    request: Request,
    catalog: Annotated[Catalog, Depends(get_catalog)],
) -> HTMLResponse:
    html = render("wizard.html", title="New Run", **_wizard_ctx(1, {}, catalog), request=request)
    return HTMLResponse(html)


@router.get("/wizard/step/{n}")
async def wizard_step_get(
    n: int,
    request: Request,
    catalog: Annotated[Catalog, Depends(get_catalog)],
) -> HTMLResponse:
    params: dict = dict(request.query_params)
    # Multi-value query params (plugin_ids, strategy_ids)
    for key in ("plugin_ids", "strategy_ids"):
        vals = request.query_params.getlist(key)
        if vals:
            params[key] = vals
    ctx = _wizard_ctx(n, params, catalog)
    return HTMLResponse(render(f"partials/wizard_step_{n}.html", **ctx))


@router.post("/wizard/step/{n}")
async def wizard_step_post(
    n: int,
    request: Request,
    catalog: Annotated[Catalog, Depends(get_catalog)],
) -> HTMLResponse:
    """Re-render step n with form data (Back navigation / completed-step edit)."""
    data = await _parse_form(request)
    ctx = _wizard_ctx(n, data, catalog)
    return HTMLResponse(render(f"partials/wizard_step_{n}.html", **ctx))


@router.post("/wizard/step/{n}/next")
async def wizard_step_next(
    n: int,
    request: Request,
    catalog: Annotated[Catalog, Depends(get_catalog)],
) -> HTMLResponse:
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
