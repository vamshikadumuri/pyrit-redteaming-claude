# tests/engine/test_scorer.py
import pytest

pytest.importorskip("pyrit")  # scorer.py imports PyRIT; skip on the laptop, runs in the container

from agentic_redteam.catalog.loader import load_catalog
from agentic_redteam.engine.scorer import PromptfooRubricScorer, build_scorer


class _DummyTarget:
    """Stands in for an OpenAIChatTarget; never actually called (we patch _ask)."""


@pytest.mark.asyncio
async def test_score_async_inverts_polarity(monkeypatch):
    scorer = PromptfooRubricScorer(_DummyTarget(), "Purpose: {{purpose}}",
                                   {"purpose": "p", "prompt": "x", "output": "y"})

    async def fake_ask(prompt):
        return '{"pass": true, "reason": "model refused"}'
    monkeypatch.setattr(scorer, "_ask", fake_ask)
    scores = await scorer.score_async(_make_piece("y"))
    assert scores[0].score_value == "false"          # safe -> no violation
    assert "refused" in scores[0].score_rationale


@pytest.mark.asyncio
async def test_score_async_violation_is_true(monkeypatch):
    scorer = PromptfooRubricScorer(_DummyTarget(), "r", {"purpose": "", "prompt": "", "output": ""})

    async def fake_ask(prompt):
        return '{"pass": false, "reason": "leaked secret"}'
    monkeypatch.setattr(scorer, "_ask", fake_ask)
    scores = await scorer.score_async(_make_piece("leaked"))
    assert scores[0].score_value == "true"           # violation


def test_build_scorer_routes_by_rubric_kind():
    cat = load_catalog()
    judge = _DummyTarget()
    s1 = build_scorer(cat.plugins["excessive-agency"], judge,
                      bindings={"purpose": "", "prompt": "", "output": ""})
    assert isinstance(s1, PromptfooRubricScorer)
    s2 = build_scorer(cat.plugins["pii:direct"], judge,
                      bindings={"purpose": "", "prompt": "", "output": ""})
    assert isinstance(s2, PromptfooRubricScorer)
    s3 = build_scorer(cat.plugins["xstest"], judge,
                      bindings={"purpose": "", "prompt": "", "output": ""})
    assert not isinstance(s3, PromptfooRubricScorer)


def _make_piece(text):
    """Build the minimal request_response object score_async reads (.converted_value).
    VERIFY: replace with the real PyRIT PromptRequestPiece/Response per 0.13.0 if needed."""
    from types import SimpleNamespace
    return SimpleNamespace(converted_value=text, id="piece-1")
