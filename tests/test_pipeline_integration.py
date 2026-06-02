# tests/test_pipeline_integration.py
import json

import pytest

from agentic_redteam.catalog.loader import load_catalog
from agentic_redteam.config import ModelConfig
from agentic_redteam.engine.plan import RunConfig
from agentic_redteam.orchestrator import Orchestrator
from agentic_redteam.records import ExecutionRecord, RunRequest
from agentic_redteam.reports.aggregation import build_report
from agentic_redteam.store import Store


def _fake_llm(reply):
    async def llm(system, user):
        return reply
    return llm


@pytest.mark.asyncio
async def test_full_pipeline_orchestrate_store_report():
    cat, store = load_catalog(), Store()

    # deterministic executor: pii:direct succeeds, bola defends -> a non-trivial scorecard
    async def executor(plan):
        status = "succeeded" if plan.plugin.id == "pii:direct" else "defended"
        return ExecutionRecord.from_plan(plan, status=status, rationale="judged")
    orch = Orchestrator(cat, store, llm=_fake_llm(json.dumps(["g1", "g2"])), executor=executor)

    req = RunRequest(
        config=RunConfig(run_id="run-1", plugin_ids=["pii:direct", "bola"],
                         strategy_ids=["basic"], n=2),
        target=ModelConfig(endpoint="https://gw/v1", model_name="t"),
        judge=ModelConfig(endpoint="https://gw/v1", model_name="j"),
        requested_by="vamshi")
    summary = await orch.run(req)

    assert summary.total == 4 and summary.succeeded == 2 and summary.status == "completed"

    report = build_report(store.get_executions("run-1"))
    assert report["overall_asr"] == 0.5
    assert report["asr_heatmap"]["pii:direct"]["basic"]["asr"] == 1.0
    assert report["asr_heatmap"]["bola"]["basic"]["asr"] == 0.0
    # pii:direct carries an OWASP LLM code -> appears in the scorecard
    assert report["framework_scorecard"]["owasp_llm"]
    # the run + audit trail persisted
    assert store.get_run("run-1")["status"] == "completed"
    assert store.get_audit("run-1")[0]["objective_count"] == 4
