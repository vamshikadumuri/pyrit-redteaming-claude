from agentic_redteam.web import render


def test_render_report_shows_asr_and_finding():
    html = render.render(
        "report.html",
        title="Report",
        ctx={
            "summary": {
                "run_id": "r1",
                "status": "completed",
                "total": 2,
                "completed": 2,
                "succeeded": 1,
                "errors": 0,
                "asr": 0.5,
            },
            "overall_asr": 0.5,
            "framework_scorecard": {
                "owasp_llm": {"LLM06": {"total": 1, "succeeded": 1, "asr": 1.0}}
            },
            "asr_heatmap": {"pii:direct": {"basic": {"total": 1, "succeeded": 1, "asr": 1.0}}},
            "findings": [
                {
                    "plugin_id": "pii:direct",
                    "strategy_id": "basic",
                    "objective": "x",
                    "severity": "high",
                    "fidelity": "text_inferred",
                    "fidelity_label": "🟡 Text-inferred",
                    "rationale": "leaked",
                    "conversation_id": "c1",
                }
            ],
            "sanity_flags": [],
            "total_executions": 2,
            "errors": 0,
        },
    )
    assert "50" in html  # ASR 50%
    assert "pii:direct" in html  # finding appears
    assert "🟡" in html  # fidelity badge


def test_render_live_has_run_id_and_progress():
    html = render.render(
        "live.html",
        title="Run r1",
        run_id="r1",
        ctx={
            "summary": {
                "run_id": "r1",
                "status": "running",
                "total": 10,
                "completed": 3,
                "succeeded": 1,
                "errors": 0,
                "asr": 0.33,
            },
            "overall_asr": 0.33,
            "framework_scorecard": {},
            "asr_heatmap": {},
            "findings": [],
            "sanity_flags": [],
            "total_executions": 3,
            "errors": 0,
        },
    )
    assert "r1" in html
    assert "3" in html and "10" in html  # progress numbers


def test_render_runs_has_run_row():
    html = render.render(
        "runs.html",
        title="Runs",
        rows=[
            {
                "run_id": "r1",
                "status": "completed",
                "requested_by": "me",
                "target_endpoint": "https://gw/v1",
                "total": 2,
                "succeeded": 1,
                "asr": 0.5,
                "created_at": 0.0,
            }
        ],
    )
    assert "r1" in html and "completed" in html


def test_render_runs_status_pill():
    html = render.render(
        "runs.html",
        title="Runs",
        rows=[
            {
                "run_id": "r2",
                "status": "running",
                "requested_by": "x",
                "target_endpoint": "http://gw/v1",
                "total": 5,
                "succeeded": 2,
                "asr": 0.4,
                "created_at": 0.0,
            }
        ],
    )
    assert "running" in html  # status appears
    assert "40%" in html  # ASR formatted
    assert "/runs/r2" in html  # view link


def test_render_report_drilldown_and_sanity():
    html = render.render(
        "report.html",
        title="R",
        ctx={
            "summary": {
                "run_id": "r1",
                "status": "completed",
                "total": 3,
                "completed": 3,
                "succeeded": 2,
                "errors": 0,
                "asr": 0.67,
            },
            "overall_asr": 0.67,
            "framework_scorecard": {
                "owasp_llm": {"LLM01": {"total": 2, "succeeded": 2, "asr": 1.0}}
            },
            "asr_heatmap": {"pii:direct": {"basic": {"total": 2, "succeeded": 2, "asr": 1.0}}},
            "findings": [
                {
                    "plugin_id": "pii:direct",
                    "strategy_id": "basic",
                    "objective": "steal PII",
                    "severity": "high",
                    "fidelity": "text_inferred",
                    "fidelity_label": "🟡 Text-inferred",
                    "rationale": "disclosed account",
                    "conversation_id": "conv-1",
                },
                {
                    "plugin_id": "harmful:hate",
                    "strategy_id": "crescendo",
                    "objective": "generate hate",
                    "severity": "critical",
                    "fidelity": "text_inferred",
                    "fidelity_label": "🟡 Text-inferred",
                    "rationale": "produced hateful content",
                    "conversation_id": "",
                },
            ],
            "sanity_flags": [{"plugin_id": "basic-test", "note": "all-pass", "asr": 1.0}],
            "total_executions": 3,
            "errors": 0,
        },
    )
    assert "steal PII" in html  # objective in drilldown
    assert "disclosed account" in html  # rationale
    assert "conv-1" in html  # conversation_id
    assert "all-pass" in html  # sanity flag
    assert "critical" in html  # severity
