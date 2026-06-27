# tests/catalog/test_models.py
from agentic_redteam.catalog.models import (
    ConverterCategory,
    FrameworkRefs,
    ObjectiveSource,
    Plugin,
    PluginType,
    Preset,
    PyritAttack,
    PyritConverter,
    Requirement,
    RubricKind,
    Severity,
    TurnType,
)


def test_plugin_defaults_and_enums():
    p = Plugin(
        id="excessive-agency",
        name="Excessive Agency",
        severity=Severity.medium,
        plugin_type=PluginType.generative,
        objective_source=ObjectiveSource.generate_locally,
        category_group="Security & Access Control",
        rubric_kind=RubricKind.llm_rubric,
    )
    assert p.severity is Severity.medium
    assert p.plugin_type is PluginType.generative
    assert p.objective_source is ObjectiveSource.generate_locally
    assert p.rubric_kind is RubricKind.llm_rubric
    assert p.framework_refs.owasp_llm == []
    assert p.runnable is True
    assert p.seed_dataset is None


def test_pyrit_attack_model():
    a = PyritAttack(
        class_name="CrescendoAttack",
        display_name="Crescendo",
        turn_type=TurnType.multi_turn,
        needs=["adversarial_chat"],
        params={"max_turns": 10},
    )
    assert a.turn_type is TurnType.multi_turn
    assert a.runnable is True
    assert "adversarial_chat" in a.needs


def test_pyrit_attack_objective_scorer_kind_defaults_to_true_false():
    a = PyritAttack(
        class_name="PromptSendingAttack",
        display_name="Prompt Sending",
        turn_type=TurnType.single_turn,
    )
    assert a.objective_scorer_kind == "true_false"


def test_pyrit_attack_objective_scorer_kind_can_be_float_scale():
    a = PyritAttack(
        class_name="PAIRAttack",
        display_name="PAIR",
        turn_type=TurnType.multi_turn,
        needs=["adversarial_chat", "objective_scorer"],
        objective_scorer_kind="float_scale",
    )
    assert a.objective_scorer_kind == "float_scale"


def test_pyrit_converter_model():
    c = PyritConverter(
        class_name="Base64Converter",
        display_name="Base64",
        category=ConverterCategory.encoding,
        requirement=Requirement.offline,
    )
    assert c.runnable is True
    assert c.requirement is Requirement.offline


def test_preset_requires_plugins():
    pr = Preset(
        id="owasp_agentic",
        framework="OWASP Agentic",
        title="OWASP Agentic Top 10",
        plugins=["excessive-agency"],
    )
    assert pr.plugins == ["excessive-agency"]


def test_framework_refs_holds_codes():
    fr = FrameworkRefs(owasp_agentic=["ASI02", "ASI10"], owasp_llm=["LLM06"])
    assert "ASI10" in fr.owasp_agentic
