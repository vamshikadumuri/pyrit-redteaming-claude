"""The PyRIT engine adapter (spec §3 component 4, §11). The ONLY module importing
PyRIT attacks/targets. Maps an AttackPlan + ModelConfigs -> live PyRIT objects and
runs execute_async. Every verified class name is isolated in the lookup tables
below; resolve the VERIFY notes in the ghcr.io/vamshikadumuri/pyrit:0.13.0-v2
container. Logic (which class, which objective/labels) lives in the pure modules."""

from __future__ import annotations

from pyrit.executor.attack import (
    AttackAdversarialConfig,
    AttackScoringConfig,
    CrescendoAttack,
    PromptSendingAttack,
    RedTeamingAttack,
    RolePlayAttack,
    TreeOfAttacksWithPruningAttack,
)
from pyrit.prompt_target import OpenAIChatTarget

from agentic_redteam.config import ModelConfig
from agentic_redteam.engine.plan import AttackPlan
from agentic_redteam.engine.scorer import build_scorer

# Module-level aliases so tests can monkeypatch the config constructors independently.
_AttackAdversarialConfig = AttackAdversarialConfig
_AttackScoringConfig = AttackScoringConfig

# name -> class. VERIFY each ctor in the container (Crescendo confirmed by crescendo.py).
_ATTACKS = {
    "PromptSendingAttack": PromptSendingAttack,
    "CrescendoAttack": CrescendoAttack,
    "RedTeamingAttack": RedTeamingAttack,
    "TreeOfAttacksWithPruningAttack": TreeOfAttacksWithPruningAttack,
    "RolePlayAttack": RolePlayAttack,
}


def build_target(config: ModelConfig) -> OpenAIChatTarget:
    kwargs: dict = dict(
        endpoint=config.endpoint, api_key=config.resolve_api_key(), model_name=config.model_name
    )
    if config.temperature is not None:
        kwargs["temperature"] = config.temperature
    return OpenAIChatTarget(**kwargs)


def _build_converters(converter_classes: list[str]) -> list:
    """VERIFY: converter imports + how PromptSendingAttack attaches them
    (request_converter_configurations / PromptConverterConfiguration). Not on the
    Crescendo smoke path. Resolve in-container before enabling converter strategies."""
    from pyrit import prompt_converter as pc

    return [getattr(pc, name)() for name in converter_classes]


def build_attack(plan: AttackPlan, *, objective_target, adversarial_chat, scorer):
    assert plan.strategy_spec.attack_class is not None
    cls = _ATTACKS[plan.strategy_spec.attack_class]
    if plan.strategy_spec.mechanism == "multi_turn":
        return cls(
            objective_target=objective_target,
            attack_adversarial_config=_AttackAdversarialConfig(target=adversarial_chat),
            attack_scoring_config=_AttackScoringConfig(objective_scorer=scorer),
            **plan.strategy_spec.params,  # e.g. max_turns/max_backtracks
        )
    if plan.strategy_spec.mechanism == "converter":
        converters = _build_converters(plan.strategy_spec.converter_classes)
        # VERIFY kwarg name for converter attachment on PromptSendingAttack:
        return cls(
            objective_target=objective_target,
            attack_scoring_config=_AttackScoringConfig(objective_scorer=scorer),
            request_converter_configurations=converters,
        )
    # mechanism == "send" (basic): direct send, scorer grades the response
    return cls(
        objective_target=objective_target,
        attack_scoring_config=_AttackScoringConfig(objective_scorer=scorer),
    )


async def execute_plan(
    plan: AttackPlan,
    *,
    target_config: ModelConfig,
    judge_config: ModelConfig,
    adversarial_config: ModelConfig | None = None,
):
    """Build targets/scorer/attack from the plan and run it. Returns the PyRIT
    AttackResult. Records observed grading fidelity from inline tool_calls."""
    objective_target = build_target(target_config)
    judge_target = build_target(judge_config)
    adversarial_chat = build_target(adversarial_config) if adversarial_config else None
    scorer = build_scorer(plan.plugin, judge_target, bindings=plan.bindings, invert=plan.invert)
    attack = build_attack(
        plan, objective_target=objective_target, adversarial_chat=adversarial_chat, scorer=scorer
    )
    try:
        result = await attack.execute_async(objective=plan.objective, memory_labels=plan.labels)
    except TypeError:
        # VERIFY: 0.13.0-v2 may not accept memory_labels on execute_async; then labels
        # are applied via the memory instance/context and reporting still queries by label.
        result = await attack.execute_async(objective=plan.objective)
    return result
