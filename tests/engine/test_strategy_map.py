from agentic_redteam.catalog.loader import load_catalog
from agentic_redteam.engine.strategy_map import combo_supported, resolve_strategy


def _strat(sid):
    return load_catalog().strategies[sid]


def test_basic_is_direct_send_prompt_sending():
    spec = resolve_strategy(_strat("basic"))
    assert spec.mechanism == "send"
    assert spec.attack_class == "PromptSendingAttack"
    assert spec.converter_classes == []
    assert spec.supported is True


def test_crescendo_is_multiturn_with_needs_and_params():
    spec = resolve_strategy(_strat("crescendo"))
    assert spec.mechanism == "multi_turn"
    assert spec.attack_class == "CrescendoAttack"
    assert "adversarial_chat" in spec.needs and "objective_scorer" in spec.needs
    assert spec.params["max_turns"] >= 1
    assert spec.supported is True


def test_clean_converter_maps_to_converter_class():
    spec = resolve_strategy(_strat("base64"))
    assert spec.mechanism == "converter"
    assert spec.converter_classes == ["Base64Converter"]
    assert spec.attack_class == "PromptSendingAttack"  # converters ride a direct send
    assert spec.supported is True


def test_redteaming_family_maps_to_redteaming_attack():
    spec = resolve_strategy(_strat("jailbreak:meta"))
    assert spec.attack_class == "RedTeamingAttack"
    assert spec.mechanism == "multi_turn"
    assert "adversarial_chat" in spec.needs


def test_tap_and_roleplay_classes():
    assert (
        resolve_strategy(_strat("jailbreak:tree")).attack_class == "TreeOfAttacksWithPruningAttack"
    )
    assert resolve_strategy(_strat("mischievous-user")).attack_class == "RolePlayAttack"


def test_custom_needed_is_unsupported():
    spec = resolve_strategy(_strat("camelcase"))
    assert spec.supported is False
    assert spec.mechanism == "unsupported"
    assert spec.note  # human-readable reason present


def test_multimodal_unsupported_in_poc():
    assert resolve_strategy(_strat("audio")).supported is False


def test_retry_is_na_and_unsupported():
    spec = resolve_strategy(_strat("retry"))
    assert spec.supported is False  # hidden from the attack picker


def test_combo_exempt_plugin_only_accepts_basic():
    cat = load_catalog()
    exempt = cat.plugins["system-prompt-override"]  # strategy_exempt == True
    assert combo_supported(exempt, resolve_strategy(_strat("basic"))) is True
    assert combo_supported(exempt, resolve_strategy(_strat("crescendo"))) is False


def test_combo_rejects_unsupported_strategy():
    cat = load_catalog()
    p = cat.plugins["excessive-agency"]
    assert combo_supported(p, resolve_strategy(_strat("camelcase"))) is False
    assert combo_supported(p, resolve_strategy(_strat("crescendo"))) is True
