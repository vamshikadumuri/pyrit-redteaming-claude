# tests/engine/test_scorer.py
import pytest

pytest.importorskip("pyrit")  # scorer.py imports PyRIT; skip on the laptop, runs in the container

from agentic_redteam.catalog.loader import load_catalog  # noqa: E402
from agentic_redteam.engine.scorer import PromptfooRubricScorer, build_scorer  # noqa: E402


class _FakeUnvalidated:
    """Stand-in for PyRIT's UnvalidatedScore: carries the raw judge verdict and
    builds a real Score via to_score (so polarity flows through our code)."""

    def __init__(self, raw_score_value, reason):
        self.raw_score_value = raw_score_value
        self.score_rationale = reason

    def to_score(self, *, score_value, score_type):
        from pyrit.models import Score

        return Score(
            score_value=score_value,
            score_value_description="",
            score_type=score_type,
            score_rationale=self.score_rationale,
            message_piece_id="piece-1",
            scorer_class_identifier={"__type__": "PromptfooRubricScorer", "__module__": "test"},
        )


class _FakePiece:
    converted_value = "the response under test"
    id = "piece-1"


def _scorer():
    return PromptfooRubricScorer(
        object(), "Purpose: {{purpose}}", {"purpose": "p", "prompt": "x", "output": "y"}
    )


@pytest.mark.asyncio
async def test_score_piece_inverts_safe_to_no_violation(monkeypatch):
    # judge says pass=True (SAFE) -> our Score must be "false" (no violation)
    sc = _scorer()

    async def fake(**kwargs):
        return _FakeUnvalidated("True", "model refused")

    monkeypatch.setattr(sc, "_score_value_with_llm", fake)

    scores = await sc._score_piece_async(_FakePiece())
    assert scores[0].score_value == "false"
    assert "refused" in scores[0].score_rationale


@pytest.mark.asyncio
async def test_score_piece_violation_is_true(monkeypatch):
    # judge says pass=False (FAIL) -> our Score must be "true" (violation)
    sc = _scorer()

    async def fake(**kwargs):
        return _FakeUnvalidated("False", "leaked secret")

    monkeypatch.setattr(sc, "_score_value_with_llm", fake)

    scores = await sc._score_piece_async(_FakePiece())
    assert scores[0].score_value == "true"


def test_build_scorer_routes_by_rubric_kind():
    cat = load_catalog()
    judge = object()
    b = {"purpose": "", "prompt": "", "output": ""}
    assert isinstance(
        build_scorer(cat.plugins["excessive-agency"], judge, bindings=b), PromptfooRubricScorer
    )
    assert isinstance(
        build_scorer(cat.plugins["pii:direct"], judge, bindings=b), PromptfooRubricScorer
    )
    # heuristic (xstest) -> SelfAskTrueFalseScorer (generic violation), not the rubric scorer
    assert not isinstance(
        build_scorer(cat.plugins["xstest"], judge, bindings=b), PromptfooRubricScorer
    )


@pytest.mark.asyncio
async def test_live_output_binding_uses_response_text(monkeypatch):
    # the rubric's {{output}} must render the actual response, not the construction blank
    sc = PromptfooRubricScorer(
        object(), "Output under test: {{output}}", {"purpose": "p", "prompt": "x", "output": ""}
    )
    captured = {}

    async def fake(**kwargs):
        captured["system_prompt"] = kwargs["system_prompt"]
        return _FakeUnvalidated("True", "ok")

    monkeypatch.setattr(sc, "_score_value_with_llm", fake)

    import types

    piece = types.SimpleNamespace(converted_value="the response under test", id="piece-1")
    await sc._score_piece_async(piece)
    assert "the response under test" in captured["system_prompt"]


@pytest.mark.asyncio
async def test_fallback_invoked_when_judge_roundtrip_fails(monkeypatch):
    sc = _scorer()

    async def boom(**kwargs):
        raise ValueError("judge returned unparseable garbage")

    monkeypatch.setattr(sc, "_score_value_with_llm", boom)

    sentinel = object()

    async def fake_fallback(message_piece, *, objective=None):
        return sentinel

    monkeypatch.setattr(sc, "_fallback_score", fake_fallback)

    result = await sc._score_piece_async(_FakePiece())
    assert result is sentinel


def test_build_scorer_dynamic_coding_is_insecure_code():
    from pyrit.score import InsecureCodeScorer

    cat = load_catalog()
    s = build_scorer(
        cat.plugins["coding-agent:core"],
        object(),
        bindings={"purpose": "", "prompt": "", "output": ""},
    )
    assert isinstance(s, InsecureCodeScorer)


def test_build_scorer_heuristic_is_selfask_not_substring():
    from pyrit.score import SelfAskTrueFalseScorer, SubStringScorer

    cat = load_catalog()
    s = build_scorer(
        cat.plugins["xstest"], object(), bindings={"purpose": "", "prompt": "", "output": ""}
    )
    assert isinstance(s, SelfAskTrueFalseScorer)
    assert not isinstance(s, SubStringScorer)
