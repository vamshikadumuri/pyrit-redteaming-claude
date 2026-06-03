import asyncio
import json

from agentic_redteam.catalog.loader import load_catalog
from agentic_redteam.config import ModelConfig
from agentic_redteam.engine.plan import AttackPlan, RunConfig
from agentic_redteam.records import ExecutionRecord, RunRequest
from agentic_redteam.store import Store
from agentic_redteam.web.manager import RunManager


def _fake_exec_factory(request):
    async def _e(plan: AttackPlan) -> ExecutionRecord:
        return ExecutionRecord.from_plan(plan, status="succeeded")
    return _e


def _fake_llm_factory(request):
    async def _llm(system: str, user: str) -> str:
        return json.dumps(["goal a", "goal b"])
    return _llm


def test_manager_runs_to_completion_and_persists():
    cat, store = load_catalog(), Store()
    mgr = RunManager(cat, store, executor_factory=_fake_exec_factory,
                     llm_factory=_fake_llm_factory)
    m = ModelConfig(endpoint="http://t/v1", model_name="t")
    req = RunRequest(
        config=RunConfig(run_id="r1", plugin_ids=["pii:direct"],
                         strategy_ids=["basic"], n=2),
        target=m, judge=m, requested_by="t",
    )

    async def go():
        run_id = mgr.start(req)
        await mgr.wait(run_id)
        return run_id

    rid = asyncio.run(go())
    assert store.get_run(rid)["status"] == "completed"
    assert len(store.get_executions(rid)) == 2


def test_manager_stop_cancels_pending():
    cat, store = load_catalog(), Store()

    async def _slow_exec(plan: AttackPlan) -> ExecutionRecord:
        await asyncio.sleep(5)   # will be stopped before completing
        return ExecutionRecord.from_plan(plan, status="succeeded")

    mgr = RunManager(cat, store,
                     executor_factory=lambda req: _slow_exec,
                     llm_factory=_fake_llm_factory)
    m = ModelConfig(endpoint="http://t/v1", model_name="t")
    req = RunRequest(
        config=RunConfig(run_id="r2", plugin_ids=["pii:direct"],
                         strategy_ids=["basic"], n=3),
        target=m, judge=m, requested_by="t",
    )

    async def go():
        mgr.start(req)
        await asyncio.sleep(0.05)   # let it start
        mgr.stop("r2")
        await mgr.wait("r2")

    asyncio.run(go())
    run = store.get_run("r2")
    assert run["status"] == "stopped"
