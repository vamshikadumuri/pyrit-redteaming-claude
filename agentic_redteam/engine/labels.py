"""Build PyRIT memory_labels for a single execution. All values are strings
(PyRIT requires str labels). Reports query memory back by these labels."""

from __future__ import annotations

import hashlib


def build_memory_labels(
    *,
    run_id: str,
    plugin_id: str,
    attack_class_name: str,
    converter_class_names: list[str],
    objective: str,
) -> dict[str, str]:
    objective_id = hashlib.sha1(objective.encode("utf-8")).hexdigest()[:12]
    return {
        "run_id": run_id,
        "plugin": plugin_id,
        "attack": attack_class_name,
        "converters": ",".join(converter_class_names) if converter_class_names else "",
        "objective": objective[:200],
        "objective_id": objective_id,
    }
