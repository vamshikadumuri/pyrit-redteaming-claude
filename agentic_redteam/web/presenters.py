"""Pure view-models for the web layer (spec §13/§14). No FastAPI, no PyRIT —
jinja2/pydantic only, so laptop-tested. Turns engine/store objects into plain dicts
the templates render. ASR/scorecard come from reports.aggregation (single source)."""

from __future__ import annotations

import json

from agentic_redteam.catalog.loader import Catalog
from agentic_redteam.catalog.models import Fidelity, StrategyKind
from agentic_redteam.engine.strategy_map import resolve_strategy
from agentic_redteam.engine.trajectory import fidelity_label
from agentic_redteam.records import ExecutionRecord, RunSummary
from agentic_redteam.reports import aggregation

_FIDELITY_BADGE = {
    Fidelity.clean: "✓",
    Fidelity.approximate: "⚠",
    Fidelity.custom_needed: "✕",
    Fidelity.na: "✕",
    Fidelity.meta: "⤬",
}


def report_context(summary: RunSummary, records: list[ExecutionRecord]) -> dict:
    report = aggregation.build_report(records)
    findings = [{**f, "fidelity_label": fidelity_label(f["fidelity"])} for f in report["findings"]]
    return {
        "summary": {
            "run_id": summary.run_id,
            "status": summary.status,
            "total": summary.total,
            "completed": summary.completed,
            "succeeded": summary.succeeded,
            "errors": summary.errors,
            "asr": summary.asr,
        },
        "overall_asr": report["overall_asr"],
        "framework_scorecard": report["framework_scorecard"],
        "asr_heatmap": report["asr_heatmap"],
        "findings": findings,
        "all_executions": report["all_executions"],
        "sanity_flags": report["sanity_flags"],
        "total_executions": report["total_executions"],
        "succeeded_count": report["succeeded_count"],
        "defended_count": report["defended_count"],
        "errors": report["errors"],
    }


def wizard_view(catalog: Catalog) -> dict:
    """View-model for the run wizard (spec §10/§13). Pure."""
    presets = [
        {
            "id": p.id,
            "title": p.title,
            "framework": p.framework,
            "plugin_count": len(p.plugins),
            "recommended_strategies": p.recommended_strategies,
        }
        for p in catalog.presets.values()
    ]
    groups = {
        group: [
            {
                "id": pl.id,
                "name": pl.name,
                "severity": pl.severity.value,
                "runnable": pl.runnable,
                "runnable_reason": pl.runnable_reason,
                "strategy_exempt": pl.strategy_exempt,
                "plugin_type": pl.plugin_type.value,
            }
            for pl in plugins
        ]
        for group, plugins in catalog.plugins_by_group().items()
    }
    strategies = []
    for s in catalog.strategies.values():
        if s.kind == StrategyKind.utility or s.id == "retry":
            continue
        spec = resolve_strategy(s)
        strategies.append(
            {
                "id": s.id,
                "display_name": s.display_name,
                "fidelity": spec.fidelity.value,
                "badge": _FIDELITY_BADGE.get(spec.fidelity, "?"),
                "supported": spec.supported,
                "disabled": not spec.supported,
                "note": spec.note,
                "is_multi_turn": spec.mechanism == "multi_turn",
            }
        )
    return {"presets": presets, "groups": groups, "strategies": strategies}


def run_list_view(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        s = json.loads(r.get("summary_json") or "{}")
        total, succ, comp, err = (
            s.get("total", 0),
            s.get("succeeded", 0),
            s.get("completed", 0),
            s.get("errors", 0),
        )
        graded = comp - err
        out.append(
            {
                "run_id": r["run_id"],
                "status": r["status"],
                "requested_by": r.get("requested_by", ""),
                "target_endpoint": r.get("target_endpoint", ""),
                "total": total,
                "succeeded": succ,
                "asr": (succ / graded) if graded else 0.0,
                "created_at": r.get("created_at", 0.0),
            }
        )
    return out
