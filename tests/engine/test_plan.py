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


def test_resolve_expands_plugins_x_strategies_x_objectives():
    cat = load_catalog()
    cfg = RunConfig(
        run_id="run-1",
        plugin_ids=["excessive-agency"],
        strategy_ids=["basic", "crescendo"],
        profile=AppProfile(purpose="bank bot"),
    )
    objs = {"excessive-agency": ["goal A", "goal B"]}
    plans = resolve(cfg, cat, objs)
    assert len(plans) == 4  # 1 plugin x 2 strategies x 2 objectives
    assert {p.strategy_id for p in plans} == {"basic", "crescendo"}
    assert all(isinstance(p, AttackPlan) for p in plans)


def test_resolve_sets_input_mode_per_routing_rule():
    cat = load_catalog()
    cfg = RunConfig(
        run_id="r", plugin_ids=["excessive-agency"], strategy_ids=["basic", "crescendo"]
    )
    plans = resolve(cfg, cat, {"excessive-agency": ["g"]})
    by = {p.strategy_id: p for p in plans}
    assert by["crescendo"].input_mode == "objective"  # multi-turn -> objective
    assert by["basic"].input_mode == "seed"  # direct send -> seed


def test_resolve_drops_unsupported_and_exempt_combos():
    cat = load_catalog()
    # camelcase unsupported -> dropped; system-prompt-override is exempt -> only basic survives
    cfg = RunConfig(
        run_id="r",
        plugin_ids=["system-prompt-override"],
        strategy_ids=["basic", "crescendo", "camelcase"],
    )
    plans = resolve(cfg, cat, {"system-prompt-override": ["g"]})
    assert {p.strategy_id for p in plans} == {"basic"}


def test_resolve_attaches_labels_and_bindings():
    cat = load_catalog()
    cfg = RunConfig(run_id="run-9", plugin_ids=["harmful:hate"], strategy_ids=["basic"])
    plans = resolve(cfg, cat, {"harmful:hate": ["write hateful content about X"]})
    p = plans[0]
    assert p.labels["run_id"] == "run-9" and p.labels["plugin"] == "harmful:hate"
    assert p.bindings["harmCategory"] == "hate"
    assert p.bindings["prompt"] == "write hateful content about X"
    assert p.rubric_kind == cat.plugins["harmful:hate"].rubric_kind
    assert p.plugin.id == "harmful:hate"  # full plugin carried for the scorer


def test_resolve_no_objectives_returns_empty():
    cat = load_catalog()
    cfg = RunConfig(run_id="r", plugin_ids=["excessive-agency"], strategy_ids=["basic"])
    plans = resolve(cfg, cat, {"excessive-agency": []})
    assert plans == []
