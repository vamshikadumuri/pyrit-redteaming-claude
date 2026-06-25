"""The PyRIT engine adapter. The ONLY module importing PyRIT attacks/targets.
Maps AttackPlan + ModelConfigs -> live PyRIT objects and runs via AttackExecutor.
Targets PyRIT 0.14.0+."""

from __future__ import annotations

import logging

from pyrit.executor.attack import (
    AttackAdversarialConfig,
    AttackConverterConfig,
    AttackExecutor,
    AttackScoringConfig,
    BargeInAttack,
    ChunkedRequestAttack,
    ContextComplianceAttack,
    CrescendoAttack,
    FlipAttack,
    ManyShotJailbreakAttack,
    MultiPromptSendingAttack,
    PAIRAttack,
    PromptSendingAttack,
    RedTeamingAttack,
    RolePlayAttack,
    SkeletonKeyAttack,
    TreeOfAttacksWithPruningAttack,
)
from pyrit.prompt_target import OpenAIChatTarget

from agentic_redteam.config import ModelConfig
from agentic_redteam.engine.plan import AttackPlan
from agentic_redteam.engine.scorer import build_scorer

logger = logging.getLogger(__name__)

# Module-level aliases so tests can monkeypatch independently.
_AttackAdversarialConfig = AttackAdversarialConfig
_AttackScoringConfig = AttackScoringConfig
_AttackConverterConfig = AttackConverterConfig

# name -> class. Covers all 13 runnable attacks from pyrit_attacks.json.
# VERIFY ctor signatures in-container before relying on newly-added attacks.
_ATTACKS = {
    "PromptSendingAttack": PromptSendingAttack,
    "MultiPromptSendingAttack": MultiPromptSendingAttack,
    "CrescendoAttack": CrescendoAttack,
    "RedTeamingAttack": RedTeamingAttack,
    "PAIRAttack": PAIRAttack,
    "TreeOfAttacksWithPruningAttack": TreeOfAttacksWithPruningAttack,
    "RolePlayAttack": RolePlayAttack,
    "SkeletonKeyAttack": SkeletonKeyAttack,
    "ManyShotJailbreakAttack": ManyShotJailbreakAttack,
    "FlipAttack": FlipAttack,
    "ContextComplianceAttack": ContextComplianceAttack,
    "BargeInAttack": BargeInAttack,
    "ChunkedRequestAttack": ChunkedRequestAttack,
}


def build_target(config: ModelConfig) -> OpenAIChatTarget:
    logger.debug(
        "Building OpenAIChatTarget endpoint=%s model=%s", config.endpoint, config.model_name
    )
    kwargs: dict = dict(
        endpoint=config.endpoint, api_key=config.resolve_api_key(), model_name=config.model_name
    )
    if config.temperature is not None:
        kwargs["temperature"] = config.temperature
    return OpenAIChatTarget(**kwargs)


def _build_converters(converter_class_names: list[str], *, converter_target=None) -> list:
    from pyrit import prompt_converter as pc

    out = []
    for name in converter_class_names:
        cls = getattr(pc, name)
        try:
            # LLM-backed converters accept a converter_target; offline ones do not.
            # VERIFY exact param name in-container.
            out.append(cls(converter_target=converter_target) if converter_target else cls())
        except TypeError:
            out.append(cls())
    return out


def build_attack(plan: AttackPlan, *, objective_target, adversarial_chat, scorer):
    cls = _ATTACKS[plan.attack.class_name]
    kwargs: dict = {
        "objective_target": objective_target,
        "attack_scoring_config": _AttackScoringConfig(objective_scorer=scorer),
    }
    if "adversarial_chat" in plan.attack.needs:
        kwargs["attack_adversarial_config"] = _AttackAdversarialConfig(target=adversarial_chat)
    if plan.converters:
        built = _build_converters(
            [c.class_name for c in plan.converters],
            converter_target=adversarial_chat,
        )
        # VERIFY: exact kwarg for AttackConverterConfig in-container.
        kwargs["attack_converter_config"] = _AttackConverterConfig(request_converters=built)
    kwargs.update(plan.attack.params)
    return cls(**kwargs)


async def execute_plan(
    plan: AttackPlan,
    *,
    target_config: ModelConfig,
    judge_config: ModelConfig,
    adversarial_config: ModelConfig | None = None,
):
    """Build targets/scorer/attack from the plan and run it. Returns the PyRIT AttackResult."""
    objective_target = build_target(target_config)
    judge_target = build_target(judge_config)
    adversarial_chat = build_target(adversarial_config) if adversarial_config else None
    scorer = build_scorer(plan.plugin, judge_target, bindings=plan.bindings, invert=plan.invert)
    attack = build_attack(
        plan, objective_target=objective_target, adversarial_chat=adversarial_chat, scorer=scorer
    )
    executor = AttackExecutor()
    results = await executor.execute_attack_async(attack=attack, objectives=[plan.objective])
    return results.get_results()[0]
