from agentic_redteam.records import ExecutionRecord, RunSummary
from agentic_redteam.web import presenters


def _rec(**kw):
    base: dict = dict(
        run_id="r1",
        plugin_id="pii:direct",
        attack_class_name="PromptSendingAttack",
        objective_id="o1",
        objective="exfiltrate PII",
        status="succeeded",
        rationale="leaked",
        fidelity="text_inferred",
        severity="high",
        framework_refs={"owasp_llm": ["LLM06"]},
    )
    base.update(kw)
    return ExecutionRecord(**base)


def test_report_context_has_scorecard_findings_and_badges():
    recs = [_rec(), _rec(objective_id="o2", status="defended")]
    ctx = presenters.report_context(
        RunSummary(run_id="r1", status="completed", total=2, completed=2, succeeded=1), recs
    )
    assert ctx["overall_asr"] == 0.5
    assert "Text-inferred" in ctx["findings"][0]["fidelity_label"]
    assert "LLM06" in ctx["framework_scorecard"]["owasp_llm"]
    assert ctx["summary"]["asr"] == 0.5


def test_run_list_view_shapes_rows():
    rows = presenters.run_list_view(
        [
            {
                "run_id": "r1",
                "status": "completed",
                "requested_by": "me",
                "target_endpoint": "https://gw/v1",
                "summary_json": '{"total":2,"succeeded":1,"completed":2,"errors":0}',
                "created_at": 1.0,
            }
        ]
    )
    assert rows[0]["run_id"] == "r1" and rows[0]["asr"] == 0.5 and rows[0]["succeeded"] == 1


def test_run_list_view_handles_missing_summary_json():
    rows = presenters.run_list_view(
        [
            {
                "run_id": "r2",
                "status": "completed",
                "requested_by": "me",
                "target_endpoint": "https://gw/v1",
                "created_at": 2.0,
            }
        ]
    )
    assert rows[0]["run_id"] == "r2" and rows[0]["asr"] == 0.0 and rows[0]["succeeded"] == 0


def test_wizard_view_has_presets_groups_attacks_converters():
    from agentic_redteam.catalog.loader import load_catalog

    cat = load_catalog()
    wv = presenters.wizard_view(cat)
    # presets
    assert len(wv["presets"]) > 0
    preset_ids = [p["id"] for p in wv["presets"]]
    assert "owasp_llm" in preset_ids
    # groups
    assert len(wv["groups"]) > 0
    # attacks
    attacks = {a["class_name"]: a for a in wv["attacks"]}
    assert "PromptSendingAttack" in attacks
    assert "CrescendoAttack" in attacks
    # at least one multi-turn attack
    assert any(a["turn_type"] == "multi_turn" for a in wv["attacks"])
    # converters
    assert len(wv["converters"]) > 0
