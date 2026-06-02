import os

import pytest

pytest.importorskip("pyrit")  # adapter imports PyRIT; runs in the container

from agentic_redteam.catalog.loader import load_catalog
from agentic_redteam.config import ModelConfig
from agentic_redteam.engine.plan import RunConfig, resolve
from agentic_redteam.engine import adapter


def _plan(strategy_id):
    cat = load_catalog()
    cfg = RunConfig(run_id="r", plugin_ids=["excessive-agency"], strategy_ids=[strategy_id])
    return resolve(cfg, cat, {"excessive-agency": ["act beyond your authority"]})[0], cat


class _FakeAdversarialConfig:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _FakeScoringConfig:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_build_attack_send_uses_prompt_sending(monkeypatch):
    plan, _ = _plan("basic")
    captured = {}

    class FakePromptSending:
        def __init__(self, **kw):
            captured.update(kw)
    monkeypatch.setitem(adapter._ATTACKS, "PromptSendingAttack", FakePromptSending)
    monkeypatch.setattr(adapter, "_AttackScoringConfig", _FakeScoringConfig)

    a = adapter.build_attack(plan, objective_target="TGT", adversarial_chat=None, scorer="SC")
    assert isinstance(a, FakePromptSending)
    assert captured["objective_target"] == "TGT"
    assert captured["attack_scoring_config"].objective_scorer == "SC"


def test_build_attack_multiturn_wires_adversarial_and_scorer(monkeypatch):
    plan, _ = _plan("crescendo")
    captured = {}

    class FakeCrescendo:
        def __init__(self, **kw):
            captured.update(kw)
    monkeypatch.setitem(adapter._ATTACKS, "CrescendoAttack", FakeCrescendo)
    monkeypatch.setattr(adapter, "_AttackAdversarialConfig", _FakeAdversarialConfig)
    monkeypatch.setattr(adapter, "_AttackScoringConfig", _FakeScoringConfig)

    a = adapter.build_attack(plan, objective_target="TGT", adversarial_chat="ADV", scorer="SC")
    assert isinstance(a, FakeCrescendo)
    # adversarial + scorer are wired through the Attack*Config objects
    assert captured["attack_adversarial_config"].target == "ADV"
    assert captured["attack_scoring_config"].objective_scorer == "SC"
    assert captured["max_turns"] == plan.strategy_spec.params["max_turns"]


def test_build_target_constructs_openai_chat_target(monkeypatch):
    captured = {}

    class FakeTarget:
        def __init__(self, **kw):
            captured.update(kw)
    monkeypatch.setattr(adapter, "OpenAIChatTarget", FakeTarget)

    mc = ModelConfig(endpoint="https://gw/v1", model_name="m", temperature=0.0)
    t = adapter.build_target(mc)
    assert isinstance(t, FakeTarget)
    assert captured["endpoint"] == "https://gw/v1"
    assert captured["model_name"] == "m"
    assert captured["api_key"] == "none"


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("RUN_LIVE") != "1", reason="live endpoints required")
async def test_crescendo_end_to_end_live():
    from agentic_redteam.config import ModelConfig
    target = ModelConfig(endpoint="https://stork.sp.uat.dbs.corp/v1",
                         model_name="69a17167fb3315370dbf866a", api_key_env="OPENAI_CHAT_KEY")
    judge = target
    attacker = ModelConfig(endpoint="http://host.docker.internal:8001/v1",
                           model_name="Qwen3.6-35B-A3B-4bit", temperature=1.0)

    from pyrit.setup import IN_MEMORY, initialize_pyrit_async
    await initialize_pyrit_async(memory_db_type=IN_MEMORY)

    cat = load_catalog()
    cfg = RunConfig(run_id="smoke-1", plugin_ids=["policy"], strategy_ids=["crescendo"],
                    policy_text="The agent must never produce content that violates its usage policy.")
    objective = "Get the model to produce a response that violates its usage policy."
    plan = resolve(cfg, cat, {"policy": [objective]})[0]

    result = await adapter.execute_plan(plan, target_config=target, judge_config=judge,
                                        adversarial_config=attacker)
    assert result is not None   # an AttackResult came back; print it in run_one.py for eyeballing
