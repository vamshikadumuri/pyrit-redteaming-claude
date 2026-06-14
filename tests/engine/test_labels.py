from agentic_redteam.engine.labels import build_memory_labels


def test_labels_are_all_strings_and_carry_core_keys():
    labels = build_memory_labels(
        run_id="run-7",
        plugin_id="pii:direct",
        strategy_id="crescendo",
        objective="Leak a customer's card number",
    )
    assert labels["run_id"] == "run-7"
    assert labels["plugin"] == "pii:direct"
    assert labels["strategy"] == "crescendo"
    assert labels["objective"].startswith("Leak a customer")
    assert len(labels["objective_id"]) == 12  # short stable hash
    assert labels["fidelity"] == "text_inferred"  # planned default
    assert all(isinstance(v, str) for v in labels.values())


def test_objective_id_is_stable_and_distinct():
    a = build_memory_labels(run_id="r", plugin_id="p", strategy_id="s", objective="same goal")
    b = build_memory_labels(run_id="r", plugin_id="p", strategy_id="s", objective="same goal")
    c = build_memory_labels(run_id="r", plugin_id="p", strategy_id="s", objective="other goal")
    assert a["objective_id"] == b["objective_id"]
    assert a["objective_id"] != c["objective_id"]


def test_long_objective_text_is_truncated():
    labels = build_memory_labels(run_id="r", plugin_id="p", strategy_id="s", objective="x" * 500)
    assert len(labels["objective"]) <= 200


def test_explicit_fidelity_overrides_default():
    labels = build_memory_labels(
        run_id="r", plugin_id="p", strategy_id="s", objective="g", fidelity="action_verified"
    )
    assert labels["fidelity"] == "action_verified"
