"""Shared helpers and constants for web routes.

Extracted from app.py to avoid circular imports when router modules import
from both app.py and each other.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from uuid import uuid4

from starlette.requests import Request

from agentic_redteam.config import ModelConfig
from agentic_redteam.engine.plan import RunConfig
from agentic_redteam.engine.profile import AppProfile
from agentic_redteam.records import RunRequest

_log = logging.getLogger(__name__)

_STATIC = Path(__file__).resolve().parent / "static"
_FINAL = {"completed", "stopped", "failed"}

# ── Step fields per wizard step (used to exclude them from hidden inputs) ──
_STEP_FIELDS: dict[int, set[str]] = {
    1: {"target_endpoint", "target_model", "target_api_key_env"},
    2: {"preset", "plugin_ids", "attack_ids", "converter_ids", "scope_mode"},
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
    default_temp = 1.0 if prefix == "adversarial" else None
    return ModelConfig(
        endpoint=endpoint,
        model_name=form.get(f"{prefix}_model", ""),
        api_key_env=form.get(f"{prefix}_api_key_env", ""),
        temperature=float(temp_str) if temp_str else default_temp,
    )


def _sse(event: str, html: str) -> str:
    # SSE format: event name + single-line data (strip internal newlines)
    payload = html.replace("\n", " ").replace("\r", "")
    return f"event: {event}\ndata: {payload}\n\n"


def _build_run_request(data: dict, catalog) -> tuple[str, RunRequest]:
    """Build a RunRequest from a flat dict (form or JSON body)."""
    raw_id = (data.get("run_id") or "").strip()
    run_id = raw_id if raw_id else f"run_{uuid4().hex[:8]}"

    preset_id = (data.get("preset") or "").strip()
    if preset_id:
        preset = catalog.presets[preset_id]
        plugin_ids = list(preset.plugins)
        raw_attacks = data.get("attack_ids", [])
        attack_class_names = raw_attacks if isinstance(raw_attacks, list) else _csv(raw_attacks)
        raw_converters = data.get("converter_ids", [])
        converter_class_names = (
            raw_converters if isinstance(raw_converters, list) else _csv(raw_converters)
        )
    else:
        raw_plugins = data.get("plugin_ids", [])
        plugin_ids = raw_plugins if isinstance(raw_plugins, list) else _csv(raw_plugins)
        raw_attacks = data.get("attack_ids", [])
        attack_class_names = raw_attacks if isinstance(raw_attacks, list) else _csv(raw_attacks)
        raw_converters = data.get("converter_ids", [])
        converter_class_names = (
            raw_converters if isinstance(raw_converters, list) else _csv(raw_converters)
        )

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

    # Default to PromptSendingAttack if no attack selected (keeps the run runnable)
    if not attack_class_names:
        attack_class_names = ["PromptSendingAttack"]

    config = RunConfig(
        run_id=run_id,
        plugin_ids=plugin_ids,
        attack_class_names=attack_class_names,
        converter_class_names=converter_class_names,
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


def _make_sse_generator(run_id: str, request: Request, store, manager):
    """Return an async generator that streams SSE events for a run."""

    async def generate():
        q, unsub = manager.bus.subscribe()
        _log.info("SSE client connected for run %s", run_id)
        try:
            # Replay already-completed executions from the store
            for rec in await store.get_executions(run_id):
                from agentic_redteam.web.render import render

                html = render(
                    "partials/feed_row.html",
                    plugin_id=rec.plugin_id,
                    attack_class_name=rec.attack_class_name,
                    status=rec.status,
                )
                yield _sse("execution_done", html)

            # Check if run is already final
            row = await store.get_run(run_id)
            if row and row.get("status") in _FINAL:
                from agentic_redteam.web.render import render

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
                    from agentic_redteam.web.render import render

                    html = render(
                        "partials/feed_row.html",
                        plugin_id=event.plugin_id,
                        attack_class_name=event.attack_class_name,
                        status=event.status,
                    )
                    yield _sse("execution_done", html)
                elif event.kind == "run_finished":
                    row = await store.get_run(run_id)
                    final_status = row["status"] if row else "completed"
                    from agentic_redteam.web.render import render

                    html = render("partials/run_finished.html", run_id=run_id, status=final_status)
                    yield _sse("run_finished", html)
                    break
                else:
                    d = event.model_dump()
                    yield _sse(event.kind, json.dumps(d))
        finally:
            _log.info("SSE client disconnected for run %s", run_id)
            unsub()

    return generate
