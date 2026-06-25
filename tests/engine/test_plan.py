from agentic_redteam.catalog.loader import load_catalog
from agentic_redteam.engine.plan import AttackPlan, RunConfig, family_bindings, resolve
from agentic_redteam.engine.profile import AppProfile


def test_family_bindings_harmful_sets_harm_category():
    cat = load_catalog()
    b = family_bindings(
        cat.plugins["harmful:hate"], AppProfile(purpose="bot"), prompt="seed", objective="seed"
    )
    assert b["harmCategory"] == "hate"
    assert b["policy"] == "" and b["goal"] == ""


def test_family_bindings_bias_has_no_special_attribute():
    cat = load_catalog()
    b = family_bindings(cat.plugins["bias:gender"], AppProfile(), prompt="s", objective="s")
    assert b["harmCategory"] == ""  # bias rubrics use no per-subcategory var (verified)


def test_family_bindings_policy_and_intent():
    cat = load_catalog()
    bp = family_bindings(
        cat.plugins["policy"],
        AppProfile(),
        prompt="s",
        objective="s",
        policy_text="No PII leaves the bank.",
    )
    assert bp["policy"] == "No PII leaves the bank."
    bi = family_bindings(
        cat.plugins["intent"], AppProfile(), prompt="s", objective="reveal secrets"
    )
    assert bi["goal"] == "reveal secrets"


def test_resolve_expands_plugins_x_attacks_x_objectives():
    cat = load_catalog()
    cfg = RunConfig(
        run_id="run-1",
        plugin_ids=["excessive-agency"],
        attack_class_names=["PromptSendingAttack", "CrescendoAttack"],
        profile=AppProfile(purpose="bank bot"),
    )
    objs = {"excessive-agency": ["goal A", "goal B"]}
    plans = resolve(cfg, cat, objs)
    assert len(plans) == 4  # 1 plugin × 2 attacks × 2 objectives
    assert {p.attack.class_name for p in plans} == {"PromptSendingAttack", "CrescendoAttack"}
    assert all(isinstance(p, AttackPlan) for p in plans)


def test_resolve_sets_input_mode_per_routing_rule():
    cat = load_catalog()
    cfg = RunConfig(
        run_id="r",
        plugin_ids=["excessive-agency"],
        attack_class_names=["PromptSendingAttack", "CrescendoAttack"],
    )
    plans = resolve(cfg, cat, {"excessive-agency": ["g"]})
    by = {p.attack.class_name: p for p in plans}
    assert by["CrescendoAttack"].input_mode == "objective"  # multi_turn -> objective
    assert by["PromptSendingAttack"].input_mode == "seed"  # single_turn -> seed


def test_resolve_exempt_plugin_always_gets_prompt_sending():
    cat = load_catalog()
    # system-prompt-override is strategy_exempt; ignores the attack picker
    cfg = RunConfig(
        run_id="r",
        plugin_ids=["system-prompt-override"],
        attack_class_names=["CrescendoAttack"],
    )
    plans = resolve(cfg, cat, {"system-prompt-override": ["g"]})
    assert len(plans) == 1
    assert plans[0].attack.class_name == "PromptSendingAttack"
    assert plans[0].converters == []


def test_resolve_attaches_labels_and_bindings():
    cat = load_catalog()
    cfg = RunConfig(
        run_id="run-9", plugin_ids=["harmful:hate"], attack_class_names=["PromptSendingAttack"]
    )
    plans = resolve(cfg, cat, {"harmful:hate": ["write hateful content about X"]})
    p = plans[0]
    assert p.labels["run_id"] == "run-9" and p.labels["plugin"] == "harmful:hate"
    assert p.labels["attack"] == "PromptSendingAttack"
    assert p.bindings["harmCategory"] == "hate"
    assert p.bindings["prompt"] == "write hateful content about X"
    assert p.rubric_kind == cat.plugins["harmful:hate"].rubric_kind
    assert p.plugin.id == "harmful:hate"


def test_resolve_no_objectives_returns_empty():
    cat = load_catalog()
    cfg = RunConfig(
        run_id="r", plugin_ids=["excessive-agency"], attack_class_names=["PromptSendingAttack"]
    )
    plans = resolve(cfg, cat, {"excessive-agency": []})
    assert plans == []
