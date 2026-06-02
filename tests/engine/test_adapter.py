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
