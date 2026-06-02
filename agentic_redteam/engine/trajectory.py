"""Tool-call / trace parsing -> grading fidelity (spec §9). Pure. Phase-1 reads
inline OpenAI `tool_calls`; OTel spans, when present, also upgrade fidelity.
'Action-verified' (a tool was actually called) > 'text-inferred' (final text only)."""
from __future__ import annotations

import json

ACTION_VERIFIED = "action_verified"
TEXT_INFERRED = "text_inferred"

_LABELS = {ACTION_VERIFIED: "🟢 Action-verified", TEXT_INFERRED: "🟡 Text-inferred"}


def parse_tool_calls(message: dict) -> list[dict]:
    """Extract [{'name': str, 'arguments': dict}] from an OpenAI assistant message.
    Tolerant: a missing list -> []; unparseable arguments -> {}."""
    out: list[dict] = []
    for tc in (message or {}).get("tool_calls") or []:
        fn = tc.get("function", tc) or {}
        name = fn.get("name", "")
        raw = fn.get("arguments", "")
        if isinstance(raw, dict):
            args = raw
        else:
            try:
                args = json.loads(raw) if raw else {}
            except (json.JSONDecodeError, TypeError):
                args = {}
        out.append({"name": name, "arguments": args})
    return out


def grading_fidelity(*, tool_calls: list, otel_spans: list | None = None) -> str:
    if tool_calls or otel_spans:
        return ACTION_VERIFIED
    return TEXT_INFERRED


def fidelity_label(fidelity: str) -> str:
    return _LABELS.get(fidelity, fidelity)
