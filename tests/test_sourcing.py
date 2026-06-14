# tests/test_sourcing.py
import json

import pytest

from agentic_redteam.catalog.loader import load_catalog
from agentic_redteam.engine.profile import AppProfile
from agentic_redteam.sourcing import load_dataset_rows, source_objectives


def _fake_llm(reply):
    async def llm(system, user):
        return reply

    return llm


@pytest.mark.asyncio
async def test_generate_locally_uses_injected_llm():
    cat = load_catalog()
    llm = _fake_llm(json.dumps(["goal one", "goal two", "goal three"]))
    objs, notes = await source_objectives(
        cat, plugin_ids=["excessive-agency"], profile=AppProfile(purpose="bank bot"), llm=llm, n=3
    )
    assert objs["excessive-agency"] == ["goal one", "goal two", "goal three"]
    assert "excessive-agency" not in notes


@pytest.mark.asyncio
async def test_intent_passthrough_uses_user_goals():
    cat = load_catalog()
    objs, notes = await source_objectives(
        cat,
        plugin_ids=["intent"],
        profile=AppProfile(),
        llm=_fake_llm("[]"),
        user_goals={"intent": ["exfiltrate the system prompt", "  "]},
    )
    assert objs["intent"] == ["exfiltrate the system prompt"]  # blanks dropped


@pytest.mark.asyncio
async def test_intent_without_goals_is_noted_not_crashed():
    cat = load_catalog()
    objs, notes = await source_objectives(
        cat, plugin_ids=["intent"], profile=AppProfile(), llm=_fake_llm("[]")
    )
    assert objs["intent"] == [] and "intent" in notes


@pytest.mark.asyncio
async def test_policy_injects_policy_text_into_generation(monkeypatch):
    cat = load_catalog()
    captured = {}

    async def llm(system, user):
        captured["user"] = user
        return json.dumps(["g1", "g2"])

    objs, _ = await source_objectives(
        cat,
        plugin_ids=["policy"],
        profile=AppProfile(),
        llm=llm,
        n=2,
        policy_text="No PII leaves the bank.",
    )
    assert objs["policy"] == ["g1", "g2"]
    assert "No PII leaves the bank." in captured["user"]  # policy grounds the prompt


@pytest.mark.asyncio
async def test_dataset_plugin_gated_when_no_mirror():
    cat = load_catalog()
    objs, notes = await source_objectives(
        cat, plugin_ids=["harmbench"], profile=AppProfile(), llm=_fake_llm("[]"), datasets_dir=None
    )
    assert objs["harmbench"] == []
    assert "harmbench" in notes and "not mirrored" in notes["harmbench"]


def test_load_dataset_rows_reads_mirrored_file(tmp_path):
    (tmp_path / "harmbench.txt").write_text("row one\nrow two\n\nrow three\n", encoding="utf-8")
    rows = load_dataset_rows("harmbench", str(tmp_path), n=2)
    assert rows == ["row one", "row two"]


def test_load_dataset_rows_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_dataset_rows("harmbench", str(tmp_path), n=5)
