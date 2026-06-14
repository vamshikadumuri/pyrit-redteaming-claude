"""Build PyRIT memory_labels for a single execution (spec §11). All values are
strings (PyRIT requires str labels). Reports query memory back by these labels."""

from __future__ import annotations

import hashlib

from agentic_redteam.engine.trajectory import TEXT_INFERRED


def build_memory_labels(
    *, run_id: str, plugin_id: str, strategy_id: str, objective: str, fidelity: str = TEXT_INFERRED
) -> dict[str, str]:
    objective_id = hashlib.sha1(objective.encode("utf-8")).hexdigest()[:12]
    return {
        "run_id": run_id,
        "plugin": plugin_id,
        "strategy": strategy_id,
        "objective": objective[:200],
        "objective_id": objective_id,
        "fidelity": fidelity,
    }
