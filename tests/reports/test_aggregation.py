# tests/reports/test_aggregation.py
from agentic_redteam.records import ExecutionRecord
from agentic_redteam.reports.aggregation import (
    asr_heatmap, build_report, findings, framework_scorecard, overall_asr, sanity_flags,
)


def _rec(plugin_id, strategy_id, status, *, severity="high", refs=None, oid="o1"):
    return ExecutionRecord(run_id="r", plugin_id=plugin_id, strategy_id=strategy_id,
                           objective_id=oid, objective="obj", status=status, severity=severity,
                           framework_refs=refs or {"owasp_llm": ["LLM06"]})


def test_framework_scorecard_rolls_up_by_category_code():
    recs = [
        _rec("pii:direct", "basic", "succeeded", refs={"owasp_llm": ["LLM06"], "atlas": []}),
        _rec("pii:direct", "basic", "defended", refs={"owasp_llm": ["LLM06"], "atlas": []}, oid="o2"),
        _rec("bola", "basic", "succeeded", refs={"owasp_api": ["API01"]}, oid="o3"),
    ]
    sc = framework_scorecard(recs)
    assert sc["owasp_llm"]["LLM06"] == {"total": 2, "succeeded": 1, "asr": 0.5}
    assert sc["owasp_api"]["API01"]["asr"] == 1.0


def test_scorecard_excludes_error_records():
    recs = [_rec("pii:direct", "basic", "error", refs={"owasp_llm": ["LLM06"]}),
            _rec("pii:direct", "basic", "succeeded", refs={"owasp_llm": ["LLM06"]}, oid="o2")]
    assert framework_scorecard(recs)["owasp_llm"]["LLM06"]["total"] == 1


def test_asr_heatmap_is_plugin_by_strategy():
    recs = [_rec("pii:direct", "basic", "succeeded"),
            _rec("pii:direct", "crescendo", "defended"),
            _rec("pii:direct", "crescendo", "succeeded", oid="o2")]
    hm = asr_heatmap(recs)
    assert hm["pii:direct"]["basic"]["asr"] == 1.0
    assert hm["pii:direct"]["crescendo"] == {"total": 2, "succeeded": 1, "asr": 0.5}


def test_findings_lists_only_successes():
    recs = [_rec("pii:direct", "basic", "succeeded"), _rec("bola", "basic", "defended")]
    f = findings(recs)
    assert len(f) == 1 and f[0]["plugin_id"] == "pii:direct" and f[0]["severity"] == "high"


def test_sanity_flags_all_pass_and_all_fail():
    recs = [_rec("pii:direct", "basic", "succeeded"), _rec("pii:direct", "crescendo", "succeeded", oid="o2"),
            _rec("bola", "basic", "defended"), _rec("bola", "crescendo", "defended", oid="o3")]
    flags = {f["plugin_id"]: f["note"] for f in sanity_flags(recs)}
    assert flags == {"pii:direct": "all-pass", "bola": "all-fail"}


def test_sanity_flags_skip_single_execution_plugins():
    assert sanity_flags([_rec("pii:direct", "basic", "succeeded")]) == []


def test_overall_asr_and_build_report_shape():
    recs = [_rec("pii:direct", "basic", "succeeded"), _rec("bola", "basic", "defended"),
            _rec("ssrf", "basic", "error")]
    assert overall_asr(recs) == 0.5                    # 1 success / 2 graded (error excluded)
    rep = build_report(recs)
    assert set(rep) == {"overall_asr", "framework_scorecard", "asr_heatmap", "findings",
                        "all_executions", "sanity_flags", "total_executions",
                        "succeeded_count", "defended_count", "errors"}
    assert rep["total_executions"] == 3 and rep["errors"] == 1
    assert rep["succeeded_count"] == 1 and rep["defended_count"] == 1
