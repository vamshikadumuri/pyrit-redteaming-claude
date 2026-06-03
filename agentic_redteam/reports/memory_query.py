# agentic_redteam/reports/memory_query.py
"""CONTAINER-ONLY execution + report wiring (spec §11, §14). Two jobs:
(1) make_executor() turns the pure Orchestrator into a live one by running
    engine.adapter.execute_plan and extracting an ExecutionRecord from the PyRIT
    AttackResult (success outcome, final score, observed fidelity from tool_calls);
(2) records_from_memory() replays a past run from PyRIT memory by its run_id label
    (the spec's 'reports query memory back by labels — single source of truth' path).
Imports PyRIT — run inside ghcr.io/vamshikadumuri/pyrit:0.13.0-v2. VERIFY the
AttackResult fields + the CentralMemory query API here; the extractor degrades
gracefully (getattr fallbacks) so a name change does not crash a live run."""
from __future__ import annotations

from agentic_redteam.config import ModelConfig
from agentic_redteam.engine import adapter
from agentic_redteam.engine.plan import AttackPlan
from agentic_redteam.engine.trajectory import grading_fidelity, parse_tool_calls
from agentic_redteam.records import ExecutionRecord


def _outcome_succeeded(result) -> bool:
    """VERIFY: AttackResult.outcome enum. 0.13 uses AttackOutcome.SUCCESS for an
    achieved objective; tolerant match on the enum name/value -> 'success'."""
    outcome = getattr(result, "outcome", None)
    name = getattr(outcome, "name", None) or getattr(outcome, "value", None) or outcome
    return str(name).lower() == "success"


def _as_message_dict(response) -> dict:
    """Best-effort: reach a plain assistant message dict (with inline tool_calls)
    from AttackResult.last_response. VERIFY the Message/MessagePiece path in-container;
    a dict passes straight through, anything else -> {} (=> text-inferred fidelity)."""
    if isinstance(response, dict):
        return response
    return getattr(response, "raw_message", None) or {}


def _extract_response_text(response) -> str:
    """Best-effort text extraction from AttackResult.last_response.
    VERIFY the Message/content structure in-container."""
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        content = response.get("content", "")
        if isinstance(content, list):
            return " ".join(
                c.get("text", "") for c in content
                if isinstance(c, dict) and c.get("type") == "text"
            )
        return str(content or "")
    for attr in ("text", "content", "value"):
        val = getattr(response, attr, None)
        if isinstance(val, str) and val:
            return val
    return ""


def _result_to_record(plan: AttackPlan, result) -> ExecutionRecord:
    succeeded = _outcome_succeeded(result)
    score = getattr(result, "last_score", None)            # VERIFY field name
    rationale = str(getattr(score, "score_rationale", "")) if score is not None else ""
    score_value = str(getattr(score, "score_value", "")) if score is not None else ""
    conv_id = str(getattr(result, "conversation_id", "") or "")
    last = getattr(result, "last_response", None)          # VERIFY field name
    tool_calls = parse_tool_calls(_as_message_dict(last)) if last is not None else []
    fidelity = grading_fidelity(tool_calls=tool_calls)
    response_text = _extract_response_text(last)
    return ExecutionRecord.from_plan(
        plan, status="succeeded" if succeeded else "defended", score_value=score_value,
        rationale=rationale, fidelity=fidelity, conversation_id=conv_id,
        response_text=response_text)


def make_executor(*, target_config: ModelConfig, judge_config: ModelConfig,
                  adversarial_config: ModelConfig | None = None):
    """Build the live Executor the Orchestrator calls per plan."""
    async def _execute(plan: AttackPlan) -> ExecutionRecord:
        result = await adapter.execute_plan(
            plan, target_config=target_config, judge_config=judge_config,
            adversarial_config=adversarial_config)
        return _result_to_record(plan, result)
    return _execute


def records_from_memory(run_id: str) -> list[ExecutionRecord]:
    """Replay a run from PyRIT memory by its run_id label (spec §12 single source of
    truth). VERIFY-gated: confirm the CentralMemory accessor + label-filter API in
    the container before relying on this path. The live report reads records from the
    SQLite store, so reporting works without this; this is the re-open-past-run path."""
    from pyrit.memory import CentralMemory                 # VERIFY import path
    memory = CentralMemory.get_memory_instance()           # VERIFY accessor name
    raise NotImplementedError(
        "records_from_memory: confirm CentralMemory label-query API in the "
        "0.13.0-v2 container (carry-forward from Plan 1c) before implementing")
