# tests/engine/test_grading.py
import pytest

from agentic_redteam.catalog.models import RubricKind
from agentic_redteam.engine.grading import (
    parse_verdict, apply_polarity, build_judge_prompt, route_scorer,
)


def test_parse_clean_json():
    assert parse_verdict('{"pass": true, "reason": "safe refusal"}') == \
        {"pass": True, "reason": "safe refusal"}


def test_parse_embedded_json():
    v = parse_verdict('Sure. {"pass": false, "reason": "leaked PII"} done.')
    assert v["pass"] is False and v["reason"] == "leaked PII"


def test_parse_fenced_json():
    assert parse_verdict('```json\n{"pass": false}\n```')["pass"] is False


def test_parse_wordy_fallback():
    assert parse_verdict("Verdict: PASS — the model refused.")["pass"] is True
    assert parse_verdict("This is a clear VIOLATION of policy.")["pass"] is False
    assert parse_verdict("RESULT: fail")["pass"] is False


def test_parse_unparseable_raises():
    with pytest.raises(ValueError):
        parse_verdict("the weather is nice today")


def test_polarity_inversion_is_correct():
    # promptfoo pass=SAFE -> PyRIT true=VIOLATION
    assert apply_polarity(True, invert=True) is False    # safe -> no violation
    assert apply_polarity(False, invert=True) is True    # fail -> violation
    # invert disabled = pass-through
    assert apply_polarity(True, invert=False) is True
    assert apply_polarity(False, invert=False) is False


def test_build_judge_prompt_integrates_render():
    prompt = build_judge_prompt("Purpose: {{purpose}} Output: {{output}}",
                                {"purpose": "bot", "output": "secret leaked", "prompt": ""})
    assert "bot" in prompt and "secret leaked" in prompt
    assert '"pass"' in prompt


def test_route_scorer_per_rubric_kind():
    assert route_scorer(RubricKind.llm_rubric) == "rubric"
    assert route_scorer(RubricKind.shared_grader) == "rubric"
    assert route_scorer(RubricKind.dynamic) == "dynamic"
    assert route_scorer(RubricKind.dataset) == "substring"
    assert route_scorer(RubricKind.heuristic) == "substring"
