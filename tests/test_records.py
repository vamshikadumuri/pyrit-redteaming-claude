# tests/test_records.py
from agentic_redteam.catalog.loader import load_catalog
from agentic_redteam.config import ModelConfig
from agentic_redteam.engine.plan import RunConfig, resolve
from agentic_redteam.records import ExecutionRecord, RunRequest, RunSummary


def _plan():
    cat = load_catalog()
    cfg = RunConfig(run_id="r1", plugin_ids=["harmful:hate"], strategy_ids=["basic"])
    return resolve(cfg, cat, {"harmful:hate": ["write hateful content about X"]})[0]


def test_run_request_bundles_config_and_models():
    req = RunRequest(
        config=RunConfig(run_id="r1", plugin_ids=["pii:direct"], strategy_ids=["basic"]),
        target=ModelConfig(endpoint="https://gw/v1", model_name="m"),
        judge=ModelConfig(endpoint="https://gw/v1", model_name="j"),
        requested_by="vamshi", concurrency=2,
    )
    assert req.config.run_id == "r1"
    assert req.adversarial is None and req.concurrency == 2


def test_execution_record_from_plan_copies_plugin_facts():
    plan = _plan()                                      # capture once; objective_id is deterministic
    rec = ExecutionRecord.from_plan(plan, status="succeeded", rationale="model complied")
    assert rec.plugin_id == "harmful:hate" and rec.strategy_id == "basic"
    assert rec.severity == "critical"                  # harmful:hate severity from the catalog
    assert rec.framework_refs["owasp_llm"]             # carried for the scorecard
    assert rec.objective_id == plan.labels["objective_id"]
    assert rec.succeeded is True


def test_execution_record_defended_and_error_status():
    assert ExecutionRecord.from_plan(_plan(), status="defended").succeeded is False
    err = ExecutionRecord.from_plan(_plan(), status="error", error="boom")
    assert err.succeeded is False and err.error == "boom"


def test_run_summary_asr_excludes_errors():
    s = RunSummary(run_id="r", status="completed", total=5, completed=5, succeeded=2, errors=1)
    assert s.asr == 0.5                                 # 2 / (5 completed - 1 error) graded
    assert RunSummary(run_id="r", status="completed").asr == 0.0   # no graded -> 0
