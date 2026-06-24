# tests/ingest/test_ingest_catalog.py
import json
from pathlib import Path

from agentic_redteam.ingest.ingest_catalog import write_catalog

XLSX = Path(__file__).resolve().parents[2] / "promptfoo_plugins_catalog_1.xlsx"


def _load(tmp_path):
    write_catalog(XLSX, tmp_path)

    def j(n):
        return json.loads((tmp_path / f"{n}.json").read_text(encoding="utf-8"))

    return j("plugins"), j("presets")


def test_counts(tmp_path):
    plugins, presets = _load(tmp_path)
    assert len(plugins) == 157
    pids = {p["id"] for p in presets}
    assert pids == {
        "owasp_llm",
        "owasp_api",
        "owasp_agentic",
        "mitre_atlas",
        "nist_ai_rmf",
        "eu_ai_act",
        "foundation",
        "guardrails-eval",
        "mcp",
        "default",
    }


def test_plugin_fields(tmp_path):
    plugins, _ = _load(tmp_path)
    by_id = {p["id"]: p for p in plugins}

    ea = by_id["excessive-agency"]
    assert ea["plugin_type"] == "generative"
    assert ea["objective_source"] == "generate_locally"
    assert ea["rubric_kind"] == "llm_rubric"
    assert ea["category_group"] == "Security & Access Control"
    assert "LLM06" in ea["framework_refs"]["owasp_llm"]
    assert set(ea["framework_refs"]["owasp_agentic"]) >= {"ASI02", "ASI10"}
    assert ea["strategy_exempt"] is False
    assert ea["runnable"] is True

    bt = by_id["beavertails"]
    assert bt["plugin_type"] == "dataset"
    assert bt["strategy_exempt"] is True
    assert bt["runnable"] is False
    assert bt["rubric_kind"] == "llm_rubric"

    assert by_id["xstest"]["rubric_kind"] == "heuristic"
    assert by_id["coding-agent:secret-file-read"]["rubric_kind"] == "dynamic"
    assert by_id["pii:direct"]["rubric_kind"] == "shared_grader"
    assert by_id["bias:age"]["rubric_kind"] == "shared_grader"
    assert by_id["harmful:hate"]["rubric_kind"] == "shared_grader"
    assert by_id["system-prompt-override"]["strategy_exempt"] is True
    assert by_id["agentic:memory-poisoning"]["strategy_exempt"] is True
    assert by_id["intent"]["objective_source"] == "intent_passthrough"


def test_preset_aggregation(tmp_path):
    _, presets = _load(tmp_path)
    by_id = {p["id"]: p for p in presets}

    ag = by_id["owasp_agentic"]
    assert set(ag["plugins"]) >= {
        "hijacking",
        "excessive-agency",
        "rbac",
        "bfla",
        "bola",
        "indirect-prompt-injection",
        "mcp",
    }

    mcp = by_id["mcp"]
    assert "pii:direct" in mcp["plugins"]
    assert {"mcp", "bfla", "bola", "sql-injection", "rbac"} <= set(mcp["plugins"])


def test_all_preset_refs_are_real_plugins(tmp_path):
    plugins, presets = _load(tmp_path)
    pid = {p["id"] for p in plugins}
    for pr in presets:
        for p in pr["plugins"]:
            assert p in pid, f"{pr['id']} references unknown plugin {p}"
