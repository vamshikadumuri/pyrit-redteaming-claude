# tests/engine/test_generate.py
import pytest

from agentic_redteam.catalog.models import Plugin
from agentic_redteam.engine.profile import AppProfile
from agentic_redteam.engine.generate import (
    build_generation_prompt, parse_objectives, dedup_objectives,
    generate_objectives, source_objectives_passthrough,
)


def _plugin():
    return Plugin(id="excessive-agency", name="Excessive Agency", severity="medium",
                  plugin_type="generative", objective_source="generate_locally",
                  category_group="Security & Access Control", rubric_kind="llm_rubric",
                  risk_description="Evaluates unauthorized action prevention",
                  generation_hint="Get the target to act beyond its authority.")


def _profile():
    return AppProfile(purpose="bank travel agent", tools=["book_flight", "wire_transfer"],
                      roles=["customer", "admin"])


def test_prompt_contains_context_hint_diversity_and_format():
    system, user = build_generation_prompt(_plugin(), _profile(), n=5)
    assert "objective writer" in system.lower()
    assert "bank travel agent" in user and "wire_transfer" in user
    assert "act beyond its authority" in user
    assert "different angle" in user.lower()
    assert "JSON array" in user
    assert "5" in user


def test_prompt_includes_fewshot_when_given():
    fs = [{"hint": "h", "goals": ["example goal one", "example goal two"]}]
    _, user = build_generation_prompt(_plugin(), _profile(), n=2, fewshot=fs)
    assert "example goal one" in user


def test_parse_json_array():
    assert parse_objectives('["a", "b", "c"]', 3) == ["a", "b", "c"]


def test_parse_numbered_list_fallback_strips_preamble():
    text = "Here are the goals:\n1. First goal\n2) Second goal\n- Third goal"
    out = parse_objectives(text, 3)
    assert out == ["First goal", "Second goal", "Third goal"]


def test_dedup_exact_and_near_duplicates():
    items = ["Leak the user's password",
             "leak the   user's password",
             "Leak the users password now please",
             "Transfer money to attacker account"]
    out = dedup_objectives(items)
    assert len(out) == 2
    assert "Transfer money to attacker account" in out


@pytest.mark.asyncio
async def test_generate_returns_n_distinct():
    async def llm(system, user):
        return '["goal alpha", "goal beta", "goal gamma", "goal delta", "goal epsilon"]'
    out = await generate_objectives(_plugin(), _profile(), n=5, llm=llm)
    assert len(out) == 5


@pytest.mark.asyncio
async def test_generate_tops_up_when_short():
    calls = {"n": 0}
    async def llm(system, user):
        calls["n"] += 1
        if calls["n"] == 1:
            return '["only one goal"]'
        return '["second goal", "third goal", "fourth goal", "fifth goal", "sixth goal"]'
    out = await generate_objectives(_plugin(), _profile(), n=5, llm=llm)
    assert calls["n"] == 2
    assert len(out) == 5
    assert "only one goal" in out


@pytest.mark.asyncio
async def test_generate_dedups_model_repetition():
    async def llm(system, user):
        return '["same goal", "same goal", "same goal", "same goal", "same goal"]'
    out = await generate_objectives(_plugin(), _profile(), n=5, llm=llm)
    assert len(out) == 1


def test_passthrough_trims_empties():
    assert source_objectives_passthrough([" a ", "", "b"]) == ["a", "b"]
