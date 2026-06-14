# tests/test_orchestrator.py
import json

import pytest

from agentic_redteam.catalog.loader import load_catalog
from agentic_redteam.config import ModelConfig
from agentic_redteam.engine.plan import RunConfig
from agentic_redteam.orchestrator import Orchestrator
from agentic_redteam.records import ExecutionRecord, RunRequest
from agentic_redteam.store import Store


def _fake_llm(reply):
    async def llm(system, user):
        return reply
    return llm


def _request(plugin_ids, strategy_ids, *, concurrency=4, adversarial=True):
    return RunRequest(
        config=RunConfig(run_id="run-1", plugin_ids=plugin_ids, strategy_ids=strategy_ids, n=2),
        target=ModelConfig(endpoint="https://gw/v1", model_name="t"),
        judge=ModelConfig(endpoint="https://gw/v1", model_name="j"),
        adversarial=ModelConfig(endpoint="http://host:8001/v1", model_name="q") if adversarial else None,
        requested_by="vamshi", concurrency=concurrency,
    )


def _succeed_executor(seen=None):
    async def execute(plan):
        if seen is not None:
            seen.append(plan.strategy_id)
        return ExecutionRecord.from_plan(plan, status="succeeded", rationale="complied")
    return execute


@pytest.mark.asyncio
async def test_run_sources_resolves_executes_and_persists():
    cat, store = load_catalog(), Store()
    orch = Orchestrator(cat, store, llm=_fake_llm(json.dumps(["a", "b"])),
                        executor=_succeed_executor())
    summary = await orch.run(_request(["excessive-agency"], ["basic", "crescendo"]))
    # 1 plugin x 2 strategies x 2 objectives = 4 executions
    assert summary.total == 4 and summary.completed == 4 and summary.succeeded == 4
    assert summary.status == "completed"
    assert (await store.get_run("run-1"))["status"] == "completed"
    assert len(await store.get_executions("run-1")) == 4


@pytest.mark.asyncio
async def test_run_writes_audit_entry_with_objective_count():
    cat, store = load_catalog(), Store()
    orch = Orchestrator(cat, store, llm=_fake_llm(json.dumps(["a", "b"])),
                        executor=_succeed_executor())
    await orch.run(_request(["excessive-agency"], ["basic"]))
    audit = await store.get_audit("run-1")
    assert len(audit) == 1 and audit[0]["objective_count"] == 2
    assert audit[0]["requested_by"] == "vamshi"


@pytest.mark.asyncio
async def test_executor_failure_becomes_error_record_run_continues():
    cat, store = load_catalog(), Store()

    async def flaky(plan):
        if plan.strategy_id == "crescendo":
            raise RuntimeError("attacker endpoint down")
        return ExecutionRecord.from_plan(plan, status="defended")
    orch = Orchestrator(cat, store, llm=_fake_llm(json.dumps(["a"])), executor=flaky)
    summary = await orch.run(_request(["excessive-agency"], ["basic", "crescendo"]))
    assert summary.completed == 2 and summary.errors == 1 and summary.status == "completed"
    statuses = sorted(r.status for r in await store.get_executions("run-1"))
    assert statuses == ["defended", "error"]


@pytest.mark.asyncio
async def test_progress_events_emitted_start_perexec_finish():
    cat, store = load_catalog(), Store()
    orch = Orchestrator(cat, store, llm=_fake_llm(json.dumps(["a", "b"])),
                        executor=_succeed_executor())
    q, _ = orch.bus.subscribe()
    await orch.run(_request(["excessive-agency"], ["basic"]))
    kinds = []
    while not q.empty():
        kinds.append((await q.get()).kind)
    assert kinds[0] == "run_started" and kinds[-1] == "run_finished"
    assert kinds.count("execution_done") == 2


@pytest.mark.asyncio
async def test_concurrency_limit_is_respected():
    import asyncio
    cat, store = load_catalog(), Store()
    live, peak = 0, 0

    async def slow(plan):
        nonlocal live, peak
        live += 1
        peak = max(peak, live)
        await asyncio.sleep(0.01)
        live -= 1
        return ExecutionRecord.from_plan(plan, status="defended")
    orch = Orchestrator(cat, store, llm=_fake_llm(json.dumps(["a", "b"])), executor=slow)
    # 1 plugin x 2 strategies x 2 objectives = 4 executions, capped to 2 concurrent
    summary = await orch.run(_request(["excessive-agency"], ["basic", "crescendo"], concurrency=2))
    assert summary.total == 4 and peak <= 2            # semaphore held the line


@pytest.mark.asyncio
async def test_stop_cancels_pending_executions():
    import asyncio
    cat, store = load_catalog(), Store()

    async def slow(plan):
        await asyncio.sleep(0.02)
        return ExecutionRecord.from_plan(plan, status="defended")
    orch = Orchestrator(cat, store, llm=_fake_llm(json.dumps(["a", "b", "c", "d"])),
                        executor=slow)
    orch.stop("run-1")                                 # cancel before it starts
    summary = await orch.run(_request(["excessive-agency"], ["basic"], concurrency=1))
    assert summary.status == "stopped" and summary.completed == 0
