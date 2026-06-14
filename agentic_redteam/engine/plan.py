"""Pure planning layer (spec §11): resolve a run config + pre-sourced objectives
into concrete AttackPlans. No PyRIT import. family_bindings() is the family-aware
rubric-binding injector (spec §7.5 carry-forward)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agentic_redteam.catalog.loader import Catalog
from agentic_redteam.catalog.models import Plugin, RubricKind
from agentic_redteam.engine.grading import route_scorer
from agentic_redteam.engine.labels import build_memory_labels
from agentic_redteam.engine.profile import AppProfile
from agentic_redteam.engine.strategy_map import StrategySpec, combo_supported, resolve_strategy


class RunConfig(BaseModel):
    run_id: str
    plugin_ids: list[str]
    strategy_ids: list[str]
    profile: AppProfile = Field(default_factory=AppProfile)
    n: int = 5
    policy_text: str = ""
    invert: bool = True


class AttackPlan(BaseModel):
    run_id: str
    plugin: Plugin
    strategy_id: str
    strategy_spec: StrategySpec
    objective: str
    input_mode: str  # "objective" (multi-turn) | "seed" (single-turn/send)
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
    for plugin_id in config.plugin_ids:
        plugin = catalog.plugins[plugin_id]
        objectives = objectives_by_plugin.get(plugin_id, [])
        for strategy_id in config.strategy_ids:
            strategy = catalog.strategies[strategy_id]
            spec = resolve_strategy(strategy)
            if not combo_supported(plugin, spec):
                continue
            input_mode = "objective" if spec.mechanism == "multi_turn" else "seed"
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
                    plugin_id=plugin_id,
                    strategy_id=strategy_id,
                    objective=objective,
                )
                plans.append(
                    AttackPlan(
                        run_id=config.run_id,
                        plugin=plugin,
                        strategy_id=strategy_id,
                        strategy_spec=spec,
                        objective=objective,
                        input_mode=input_mode,
                        rubric_kind=plugin.rubric_kind,
                        scorer_route=route_scorer(plugin.rubric_kind),
                        bindings=bindings,
                        labels=labels,
                        invert=config.invert,
                    )
                )
    return plans
