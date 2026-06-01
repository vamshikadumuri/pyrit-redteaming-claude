# tests/ingest/test_ingest_catalog.py
import json
from pathlib import Path

from agentic_redteam.ingest.ingest_catalog import write_catalog

XLSX = Path(__file__).resolve().parents[2] / "promptfoo_plugins_catalog_1.xlsx"


def _load(tmp_path):
    write_catalog(XLSX, tmp_path)
    j = lambda n: json.loads((tmp_path / f"{n}.json").read_text(encoding="utf-8"))
    return j("plugins"), j("strategies"), j("presets")


def test_counts(tmp_path):
    plugins, strategies, presets = _load(tmp_path)
    assert len(plugins) == 157
    assert len(strategies) == 35
    pids = {p["id"] for p in presets}
    assert pids == {
        "owasp_llm", "owasp_api", "owasp_agentic", "mitre_atlas",
        "nist_ai_rmf", "eu_ai_act", "foundation", "guardrails-eval",
        "mcp", "default",
    }


def test_plugin_fields(tmp_path):
    plugins, _, _ = _load(tmp_path)
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


def test_strategy_fields(tmp_path):
    _, strategies, _ = _load(tmp_path)
    by_id = {s["id"]: s for s in strategies}

    cr = by_id["crescendo"]
    assert cr["type"] == "multi_turn" and cr["kind"] == "attack"
    assert cr["fidelity"] == "clean" and cr["offline"] is True

    assert by_id["base64"]["kind"] == "converter" and by_id["base64"]["type"] == "encoding"
    assert by_id["retry"]["kind"] == "utility" and by_id["retry"]["fidelity"] == "na"
    assert by_id["jailbreak:meta"]["offline"] is False
    assert by_id["basic"]["is_default"] is True
    assert by_id["layer"]["kind"] == "meta"


def test_preset_aggregation(tmp_path):
    _, _, presets = _load(tmp_path)
    by_id = {p["id"]: p for p in presets}

    ag = by_id["owasp_agentic"]
    assert set(ag["plugins"]) >= {
        "hijacking", "excessive-agency", "rbac", "bfla", "bola",
        "indirect-prompt-injection", "mcp",
    }
    assert "owasp:agentic:asi03" in ag["category_index"]

    mcp = by_id["mcp"]
    assert "pii:direct" in mcp["plugins"]
    assert {"mcp", "bfla", "bola", "sql-injection", "rbac"} <= set(mcp["plugins"])

    llm = by_id["owasp_llm"]
    assert {"jailbreak", "jailbreak-templates", "jailbreak:composite"} <= set(llm["recommended_strategies"])
    default_only = by_id["foundation"]["recommended_strategies"]
    assert {"basic", "jailbreak:meta", "jailbreak:composite"} <= set(default_only)


def test_all_preset_refs_are_real_plugins(tmp_path):
    plugins, strategies, presets = _load(tmp_path)
    pid = {p["id"] for p in plugins}
    sid = {s["id"] for s in strategies}
    for pr in presets:
        for p in pr["plugins"]:
            assert p in pid, f"{pr['id']} references unknown plugin {p}"
        for s in pr["recommended_strategies"]:
            assert s in sid, f"{pr['id']} references unknown strategy {s}"
