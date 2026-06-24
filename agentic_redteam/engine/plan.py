"""Pure planning layer: resolve a run config + pre-sourced objectives into concrete
AttackPlans. No PyRIT import. family_bindings() is the family-aware rubric-binding
injector."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agentic_redteam.catalog.loader import Catalog
from agentic_redteam.catalog.models import Plugin, PyritAttack, PyritConverter, RubricKind
from agentic_redteam.engine.grading import route_scorer
from agentic_redteam.engine.labels import build_memory_labels
from agentic_redteam.engine.profile import AppProfile


class RunConfig(BaseModel):
    run_id: str
    plugin_ids: list[str]
    attack_class_names: list[str]
    converter_class_names: list[str] = Field(default_factory=list)
    profile: AppProfile = Field(default_factory=AppProfile)
    n: int = 5
    policy_text: str = ""
    invert: bool = True


class AttackPlan(BaseModel):
    run_id: str
    plugin: Plugin
    attack: PyritAttack
    converters: list[PyritConverter] = Field(default_factory=list)
    objective: str
    input_mode: str  # "objective" (multi-turn) | "seed" (single-turn)
    rubric_kind: RubricKind
    scorer_route: str  # "rubric" | "dynamic" | "substring"
    bindings: dict
    labels: dict
    invert: bool = True


def family_bindings(
    plugin: Plugin,
    profile: AppProfile,
    *,
    prompt: str,
    objective: str = "",
    output: str = "",
    policy_text: str = "",
    conversation_transcript: str = "",
) -> dict:
    """Family-aware rubric bindings. harmful:<sub> -> harmCategory=<sub>; policy ->
    policy=<policy_text>; intent -> goal=<objective>; bias:* (and the rest) -> blanks."""
    harm = plugin.id.split(":", 1)[1] if plugin.id.startswith("harmful:") else ""
    policy = policy_text if plugin.id == "policy" else ""
    goal = objective if plugin.id == "intent" else ""
    return profile.rubric_bindings(
        prompt=prompt,
        output=output,
        harm_category=harm,
        policy=policy,
        goal=goal,
        conversation_transcript=conversation_transcript,
    )


def resolve(
    config: RunConfig, catalog: Catalog, objectives_by_plugin: dict[str, list[str]]
) -> list[AttackPlan]:
    plans: list[AttackPlan] = []
    # Resolve converter objects once (skip non-runnable)
    converters = [
        catalog.converters[c]
        for c in config.converter_class_names
        if c in catalog.converters and catalog.converters[c].runnable
    ]
    for plugin_id in config.plugin_ids:
        plugin = catalog.plugins[plugin_id]
        objectives = objectives_by_plugin.get(plugin_id, [])
        # strategy_exempt plugins always get plain PromptSendingAttack, no converters
        if plugin.strategy_exempt:
            attack = catalog.attacks["PromptSendingAttack"]
            _append_plans(plans, config, plugin, attack, [], objectives)
            continue
        for attack_class_name in config.attack_class_names:
            if attack_class_name not in catalog.attacks:
                continue
            attack = catalog.attacks[attack_class_name]
            if not attack.runnable:
                continue
            _append_plans(plans, config, plugin, attack, converters, objectives)
    return plans


def _append_plans(
    plans: list[AttackPlan],
    config: RunConfig,
    plugin: Plugin,
    attack: PyritAttack,
    converters: list[PyritConverter],
    objectives: list[str],
) -> None:
    input_mode = "objective" if attack.turn_type == "multi_turn" else "seed"
    for objective in objectives:
        bindings = family_bindings(
            plugin,
            config.profile,
            prompt=objective,
            objective=objective,
            policy_text=config.policy_text,
        )
        labels = build_memory_labels(
            run_id=config.run_id,
            plugin_id=plugin.id,
            attack_class_name=attack.class_name,
            converter_class_names=[c.class_name for c in converters],
            objective=objective,
        )
        plans.append(
            AttackPlan(
                run_id=config.run_id,
                plugin=plugin,
                attack=attack,
                converters=converters,
                objective=objective,
                input_mode=input_mode,
                rubric_kind=plugin.rubric_kind,
                scorer_route=route_scorer(plugin.rubric_kind),
                bindings=bindings,
                labels=labels,
                invert=config.invert,
            )
        )
