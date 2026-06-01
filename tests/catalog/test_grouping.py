# tests/catalog/test_grouping.py
from pathlib import Path

from agentic_redteam.catalog.grouping import category_group
from agentic_redteam.ingest.xlsx_reader import read_sheet

XLSX = Path(__file__).resolve().parents[2] / "promptfoo_plugins_catalog_1.xlsx"


def test_known_mappings():
    assert category_group("pii:direct") == "Privacy & PII"
    assert category_group("harmful:privacy") == "Privacy & PII"
    assert category_group("bias:age") == "Bias & Fairness"
    assert category_group("harmful:hate") == "Harmful Content"
    assert category_group("excessive-agency") == "Security & Access Control"
    assert category_group("bola") == "Security & Access Control"
    assert category_group("financial:sox-compliance") == "Domain Packs"
    assert category_group("coding-agent:secret-file-read") == "Agentic & RAG"
    assert category_group("beavertails") == "Datasets"
    assert category_group("intent") == "Config-required"
    assert category_group("hallucination") == "Trust, Reliability & Brand"


def test_every_plugin_gets_a_known_group():
    ids = [r["Plugin ID"] for r in read_sheet(XLSX, "Plugins")]
    groups = {category_group(i) for i in ids}
    assert "Other" not in groups, f"ungrouped ids exist; groups={groups}"
    assert len(ids) == 157
