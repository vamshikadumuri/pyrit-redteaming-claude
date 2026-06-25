# agentic_redteam/catalog/loader.py
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel

from .models import Plugin, Preset, PyritAttack, PyritConverter

_DEFAULT_DATA = Path(__file__).resolve().parent / "data"


class CatalogError(ValueError):
    """Raised when the catalog fails cross-reference validation."""


class Catalog(BaseModel):
    plugins: dict[str, Plugin]
    attacks: dict[str, PyritAttack]
    converters: dict[str, PyritConverter]
    presets: dict[str, Preset]

    def plugins_by_group(self) -> dict[str, list[Plugin]]:
        out: dict[str, list[Plugin]] = defaultdict(list)
        for p in self.plugins.values():
            out[p.category_group].append(p)
        return dict(out)


def _read(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_catalog(data_dir: str | Path | None = None) -> Catalog:
    data_dir = Path(data_dir) if data_dir is not None else _DEFAULT_DATA

    plugins = {d["id"]: Plugin(**d) for d in _read(data_dir / "plugins.json")}
    attacks = {d["class_name"]: PyritAttack(**d) for d in _read(data_dir / "pyrit_attacks.json")}
    converters = {
        d["class_name"]: PyritConverter(**d) for d in _read(data_dir / "pyrit_converters.json")
    }
    presets = {d["id"]: Preset(**d) for d in _read(data_dir / "presets.json")}

    _validate(plugins, presets)
    return Catalog(plugins=plugins, attacks=attacks, converters=converters, presets=presets)


def _validate(plugins, presets) -> None:
    for pr in presets.values():
        for pid in pr.plugins:
            if pid not in plugins:
                raise CatalogError(f"preset '{pr.id}' references unknown plugin '{pid}'")
