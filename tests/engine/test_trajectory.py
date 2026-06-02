from agentic_redteam.engine.trajectory import (
    parse_tool_calls, grading_fidelity, fidelity_label,
    ACTION_VERIFIED, TEXT_INFERRED,
)


def test_parse_openai_tool_calls():
    msg = {"role": "assistant", "content": None, "tool_calls": [
        {"type": "function", "function": {"name": "wire_transfer",
                                          "arguments": '{"amount": 9999, "to": "X"}'}},
        {"type": "function", "function": {"name": "lookup", "arguments": "{}"}},
    ]}
    calls = parse_tool_calls(msg)
    assert [c["name"] for c in calls] == ["wire_transfer", "lookup"]
    assert calls[0]["arguments"] == {"amount": 9999, "to": "X"}


def test_parse_handles_no_tool_calls_and_bad_args():
    assert parse_tool_calls({"role": "assistant", "content": "hi"}) == []
    bad = {"tool_calls": [{"function": {"name": "f", "arguments": "not-json"}}]}
    assert parse_tool_calls(bad)[0]["arguments"] == {}   # tolerant: unparseable -> {}


def test_grading_fidelity_action_verified_when_tool_calls_present():
    assert grading_fidelity(tool_calls=[{"name": "f", "arguments": {}}]) == ACTION_VERIFIED


def test_grading_fidelity_action_verified_when_otel_present():
    assert grading_fidelity(tool_calls=[], otel_spans=[{"tool.name": "f"}]) == ACTION_VERIFIED


def test_grading_fidelity_text_inferred_when_nothing():
    assert grading_fidelity(tool_calls=[], otel_spans=None) == TEXT_INFERRED


def test_fidelity_label_human_readable():
    assert "Action-verified" in fidelity_label(ACTION_VERIFIED)
    assert "Text-inferred" in fidelity_label(TEXT_INFERRED)
