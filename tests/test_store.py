# tests/test_store.py
from agentic_redteam.catalog.loader import load_catalog
from agentic_redteam.config import ModelConfig
from agentic_redteam.engine.plan import RunConfig, resolve
from agentic_redteam.records import ExecutionRecord, RunRequest, RunSummary
from agentic_redteam.store import Store


def _request(run_id="run-1"):
    return RunRequest(
        config=RunConfig(run_id=run_id, plugin_ids=["pii:direct"], strategy_ids=["basic"]),
        target=ModelConfig(endpoint="https://gw/v1", model_name="m"),
        judge=ModelConfig(endpoint="https://gw/v1", model_name="j"),
        requested_by="vamshi",
    )


def _record(run_id="run-1", status="succeeded"):
    cat = load_catalog()
    cfg = RunConfig(run_id=run_id, plugin_ids=["pii:direct"], strategy_ids=["basic"])
    plan = resolve(cfg, cat, {"pii:direct": ["leak a card number"]})[0]
    return ExecutionRecord.from_plan(plan, status=status, rationale="r")


def test_create_run_is_pending_and_listed():
    s = Store()
    s.create_run(_request("run-1"))
    run = s.get_run("run-1")
    assert run["status"] == "pending" and run["requested_by"] == "vamshi"
    assert run["target_endpoint"] == "https://gw/v1"
    assert [r["run_id"] for r in s.list_runs()] == ["run-1"]


def test_set_status_and_save_summary():
    s = Store()
    s.create_run(_request("run-1"))
    s.set_status("run-1", "running")
    assert s.get_run("run-1")["status"] == "running"
    s.save_summary(RunSummary(run_id="run-1", status="completed", total=3, completed=3,
                              succeeded=1, errors=0))
    assert s.get_run("run-1")["status"] == "completed"


def test_executions_roundtrip_as_records():
    s = Store()
    s.create_run(_request("run-1"))
    s.save_execution(_record("run-1", "succeeded"))
    s.save_execution(_record("run-1", "defended"))     # same key -> REPLACE (idempotent)
    recs = s.get_executions("run-1")
    assert len(recs) == 1 and recs[0].status == "defended"
    assert isinstance(recs[0], ExecutionRecord)


def test_audit_log_records_authorization():
    s = Store()
    s.create_run(_request("run-1"))
    s.add_audit(run_id="run-1", requested_by="vamshi", target_endpoint="https://gw/v1",
                objective_count=7, detail="pii:direct: ok")
    entries = s.get_audit("run-1")
    assert len(entries) == 1
    assert entries[0]["objective_count"] == 7 and entries[0]["requested_by"] == "vamshi"


def test_get_run_missing_returns_none():
    assert Store().get_run("nope") is None
