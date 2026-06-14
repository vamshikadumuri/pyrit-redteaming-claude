# tests/catalog/test_models.py
from agentic_redteam.catalog.models import (
    Fidelity,
    FrameworkRefs,
    ObjectiveSource,
    Plugin,
    PluginType,
    Preset,
    RubricKind,
    Severity,
    Strategy,
    StrategyKind,
    StrategyType,
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


def test_strategy_enums_and_defaults():
    s = Strategy(
        id="crescendo",
        display_name="Crescendo",
        type=StrategyType.multi_turn,
        kind=StrategyKind.attack,
        offline=True,
        fidelity=Fidelity.clean,
    )
    assert s.type is StrategyType.multi_turn
    assert s.kind is StrategyKind.attack
    assert s.fidelity is Fidelity.clean
    assert s.converter_chain == []
    assert s.pyrit_class is None
    assert s.is_default is False


def test_preset_requires_plugins():
    pr = Preset(
        id="owasp_agentic",
        framework="OWASP Agentic",
        title="OWASP Agentic Top 10",
        plugins=["excessive-agency"],
    )
    assert pr.plugins == ["excessive-agency"]
    assert pr.recommended_strategies == []
    assert pr.category_index == {}


def test_framework_refs_holds_codes():
    fr = FrameworkRefs(owasp_agentic=["ASI02", "ASI10"], owasp_llm=["LLM06"])
    assert "ASI10" in fr.owasp_agentic
