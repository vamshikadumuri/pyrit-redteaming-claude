from agentic_redteam.engine.labels import build_memory_labels


def test_labels_are_all_strings_and_carry_core_keys():
    labels = build_memory_labels(
        run_id="run-7",
        plugin_id="pii:direct",
        attack_class_name="CrescendoAttack",
        converter_class_names=["Base64Converter"],
        objective="Leak a customer's card number",
    )
    assert labels["run_id"] == "run-7"
    assert labels["plugin"] == "pii:direct"
    assert labels["attack"] == "CrescendoAttack"
    assert labels["converters"] == "Base64Converter"
    assert labels["objective"].startswith("Leak a customer")
    assert len(labels["objective_id"]) == 12  # short stable hash
    assert all(isinstance(v, str) for v in labels.values())


def test_objective_id_is_stable_and_distinct():
    a = build_memory_labels(
        run_id="r",
        plugin_id="p",
        attack_class_name="A",
        converter_class_names=[],
        objective="same goal",
    )
    b = build_memory_labels(
        run_id="r",
        plugin_id="p",
        attack_class_name="A",
        converter_class_names=[],
        objective="same goal",
    )
    c = build_memory_labels(
        run_id="r",
        plugin_id="p",
        attack_class_name="A",
        converter_class_names=[],
        objective="other goal",
    )
    assert a["objective_id"] == b["objective_id"]
    assert a["objective_id"] != c["objective_id"]


def test_long_objective_text_is_truncated():
    labels = build_memory_labels(
        run_id="r",
        plugin_id="p",
        attack_class_name="A",
        converter_class_names=[],
        objective="x" * 500,
    )
    assert len(labels["objective"]) <= 200


def test_empty_converters_produces_empty_string():
    labels = build_memory_labels(
        run_id="r", plugin_id="p", attack_class_name="A", converter_class_names=[], objective="g"
    )
    assert labels["converters"] == ""


def test_multiple_converters_are_csv():
    labels = build_memory_labels(
        run_id="r",
        plugin_id="p",
        attack_class_name="A",
        converter_class_names=["Base64Converter", "ROT13Converter"],
        objective="g",
    )
    assert labels["converters"] == "Base64Converter,ROT13Converter"
