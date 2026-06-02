# agentic_redteam/sourcing.py
"""Async objective sourcing (spec §6.1): route each selected plugin to its
objective source and return objectives_by_plugin for engine.plan.resolve(). Pure —
the LLM is injected (engine.generate.LLMCallable). Dataset rows load from a mirror
dir and are GATED (missing mirror -> [] + reason, never faked, spec §6.2). This is
the async sourcing wiring deferred from Plan 1c."""
from __future__ import annotations

from pathlib import Path

from agentic_redteam.catalog.loader import Catalog
from agentic_redteam.catalog.models import ObjectiveSource, Plugin
from agentic_redteam.engine.fewshot import FEWSHOT
from agentic_redteam.engine.generate import (
    LLMCallable, generate_objectives, source_objectives_passthrough,
)
from agentic_redteam.engine.profile import AppProfile


def load_dataset_rows(dataset_id: str | None, datasets_dir: str | None, n: int) -> list[str]:
    """Read up to n rows from a mirrored dataset file `<datasets_dir>/<id>.txt`.
    Raises FileNotFoundError when the mirror is absent (the caller gates on it)."""
    if not dataset_id:
        raise ValueError("dataset plugin has no seed_dataset id")
    if not datasets_dir:
        raise FileNotFoundError(f"dataset '{dataset_id}' not mirrored (no datasets_dir configured)")
    path = Path(datasets_dir) / f"{dataset_id}.txt"
    if not path.exists():
        raise FileNotFoundError(f"dataset '{dataset_id}' not mirrored at {path}")
    rows = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return rows[:n]


async def _generate(plugin: Plugin, profile: AppProfile, n: int, llm: LLMCallable,
                    policy_text: str) -> list[str]:
    if plugin.id == "policy" and policy_text:
        profile = profile.model_copy(deep=True)
        profile.extra = {**profile.extra, "Policy under test": policy_text}
    return await generate_objectives(plugin, profile, n, llm, fewshot=FEWSHOT.get(plugin.category_group))


async def source_objectives(catalog: Catalog, *, plugin_ids: list[str], profile: AppProfile,
                            llm: LLMCallable, n: int = 5,
                            user_goals: dict[str, list[str]] | None = None,
                            policy_text: str = "", datasets_dir: str | None = None,
                            ) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Returns (objectives_by_plugin, notes). `notes[plugin_id]` explains an empty
    list (un-mirrored dataset / intent without goals) for the audit log + UI."""
    user_goals = user_goals or {}
    objectives: dict[str, list[str]] = {}
    notes: dict[str, str] = {}
    for pid in plugin_ids:
        plugin = catalog.plugins[pid]
        src = plugin.objective_source
        if src == ObjectiveSource.intent_passthrough:
            objectives[pid] = source_objectives_passthrough(user_goals.get(pid, []))
            if not objectives[pid]:
                notes[pid] = "intent plugin needs user-supplied goals"
        elif src == ObjectiveSource.dataset_rows:
            try:
                objectives[pid] = load_dataset_rows(plugin.seed_dataset, datasets_dir, n)
            except (FileNotFoundError, ValueError) as e:
                objectives[pid] = []
                notes[pid] = str(e)
        else:  # generate_locally (generative plugins + policy)
            objectives[pid] = await _generate(plugin, profile, n, llm, policy_text)
            if not objectives[pid]:
                notes[pid] = "generation produced no usable objectives"
    return objectives, notes
