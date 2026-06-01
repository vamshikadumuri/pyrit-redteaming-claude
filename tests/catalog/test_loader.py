# tests/catalog/test_loader.py
from pathlib import Path

import pytest

from agentic_redteam.catalog.loader import load_catalog, CatalogError

DATA = Path("agentic_redteam/catalog/data")


def test_loads_shipped_catalog():
    cat = load_catalog()                       # default = shipped data dir
    assert len(cat.plugins) == 157
    assert len(cat.strategies) == 35
    assert len(cat.presets) == 10
    assert cat.plugins["excessive-agency"].framework_refs.owasp_llm == ["LLM06"]
    assert cat.strategies["crescendo"].fidelity.value == "clean"
    assert "hijacking" in cat.presets["owasp_agentic"].plugins


def test_plugins_by_group_helper():
    cat = load_catalog()
    groups = cat.plugins_by_group()
    assert "pii:direct" in {p.id for p in groups["Privacy & PII"]}
    assert sum(len(v) for v in groups.values()) == 157


def test_validation_rejects_unknown_preset_plugin(tmp_path):
    import json
    (tmp_path / "plugins.json").write_text(json.dumps([{
        "id": "p1", "name": "P1", "severity": "low", "plugin_type": "generative",
        "objective_source": "generate_locally", "category_group": "Other",
        "rubric_kind": "heuristic",
    }]), encoding="utf-8")
    (tmp_path / "strategies.json").write_text("[]", encoding="utf-8")
    (tmp_path / "presets.json").write_text(json.dumps([{
        "id": "bad", "framework": "X", "title": "Bad", "plugins": ["does-not-exist"],
    }]), encoding="utf-8")
    with pytest.raises(CatalogError, match="does-not-exist"):
        load_catalog(tmp_path)
