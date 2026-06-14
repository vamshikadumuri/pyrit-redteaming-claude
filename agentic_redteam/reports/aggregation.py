# agentic_redteam/reports/aggregation.py
"""Pure report aggregation (spec §14). Consumes ExecutionRecords (from the live
orchestrator's store OR replayed from PyRIT memory by memory_query) and rolls them
up into the framework scorecard, plugin x strategy ASR heatmap, findings, and
sanity flags. Error records are excluded from graded counts. No PyRIT import."""

from __future__ import annotations

from collections import defaultdict

from agentic_redteam.records import ExecutionRecord

_FAMILIES = ["owasp_llm", "owasp_agentic", "owasp_api", "atlas"]


def _asr(succeeded: int, total: int) -> float:
    return (succeeded / total) if total else 0.0


def _graded(records: list[ExecutionRecord]) -> list[ExecutionRecord]:
    return [r for r in records if r.status != "error"]


def framework_scorecard(records: list[ExecutionRecord]) -> dict:
    """family -> category_code -> {total, succeeded, asr}. Uses each record's
    framework_refs, independent of the selected preset (spec §5.2, §14)."""
    cells: dict[str, dict[str, dict]] = {
        fam: defaultdict(lambda: {"total": 0, "succeeded": 0}) for fam in _FAMILIES
    }
    for r in _graded(records):
        for fam in _FAMILIES:
            for code in r.framework_refs.get(fam, []):
                cell = cells[fam][code]
                cell["total"] += 1
                cell["succeeded"] += int(r.succeeded)
    return {
        fam: {
            code: {
                "total": c["total"],
                "succeeded": c["succeeded"],
                "asr": _asr(c["succeeded"], c["total"]),
            }
            for code, c in codes.items()
        }
        for fam, codes in cells.items()
    }


def asr_heatmap(records: list[ExecutionRecord]) -> dict:
    """plugin_id -> strategy_id -> {total, succeeded, asr}."""
    cells: dict[tuple[str, str], dict] = defaultdict(lambda: {"total": 0, "succeeded": 0})
    for r in _graded(records):
        c = cells[(r.plugin_id, r.strategy_id)]
        c["total"] += 1
        c["succeeded"] += int(r.succeeded)
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for (pid, sid), c in cells.items():
        out[pid][sid] = {
            "total": c["total"],
            "succeeded": c["succeeded"],
            "asr": _asr(c["succeeded"], c["total"]),
        }
    return dict(out)


def findings(records: list[ExecutionRecord]) -> list[dict]:
    return [
        {
            "plugin_id": r.plugin_id,
            "strategy_id": r.strategy_id,
            "objective": r.objective,
            "severity": r.severity,
            "fidelity": r.fidelity,
            "rationale": r.rationale,
            "score_value": r.score_value,
            "response_text": r.response_text,
            "conversation_id": r.conversation_id,
        }
        for r in records
        if r.succeeded
    ]


def all_executions(records: list[ExecutionRecord]) -> list[dict]:
    """All execution records ordered by status (succeeded first) for the transparency table."""
    order = {"succeeded": 0, "defended": 1, "error": 2}
    sorted_records = sorted(records, key=lambda r: (order.get(r.status, 9), r.plugin_id))
    return [
        {
            "plugin_id": r.plugin_id,
            "strategy_id": r.strategy_id,
            "objective": r.objective,
            "status": r.status,
            "score_value": r.score_value,
            "rationale": r.rationale,
            "response_text": r.response_text,
            "error": r.error,
        }
        for r in sorted_records
    ]


def sanity_flags(records: list[ExecutionRecord]) -> list[dict]:
    """Flag any plugin with >=2 graded executions all at 0% or 100% ASR (spec §7.7)."""
    by_plugin: dict[str, dict] = defaultdict(lambda: {"total": 0, "succeeded": 0})
    for r in _graded(records):
        c = by_plugin[r.plugin_id]
        c["total"] += 1
        c["succeeded"] += int(r.succeeded)
    flags = []
    for pid, c in by_plugin.items():
        if c["total"] >= 2 and c["succeeded"] in (0, c["total"]):
            flags.append(
                {
                    "plugin_id": pid,
                    "asr": _asr(c["succeeded"], c["total"]),
                    "note": "all-pass" if c["succeeded"] == c["total"] else "all-fail",
                }
            )
    return flags


def overall_asr(records: list[ExecutionRecord]) -> float:
    graded = _graded(records)
    return _asr(sum(int(r.succeeded) for r in graded), len(graded))


def build_report(records: list[ExecutionRecord]) -> dict:
    """The full JSON report (spec §14). Printable HTML/PDF export is Plan 3 (web)."""
    graded = _graded(records)
    succeeded_count = sum(1 for r in graded if r.succeeded)
    defended_count = len(graded) - succeeded_count
    errors_count = sum(1 for r in records if r.status == "error")
    return {
        "overall_asr": overall_asr(records),
        "framework_scorecard": framework_scorecard(records),
        "asr_heatmap": asr_heatmap(records),
        "findings": findings(records),
        "all_executions": all_executions(records),
        "sanity_flags": sanity_flags(records),
        "total_executions": len(records),
        "succeeded_count": succeeded_count,
        "defended_count": defended_count,
        "errors": errors_count,
    }
