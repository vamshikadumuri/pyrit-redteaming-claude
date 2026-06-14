# tests/reports/test_memory_query.py
import pytest

pytest.importorskip("pyrit")  # imports engine.adapter (PyRIT); runs in the container

from agentic_redteam.catalog.loader import load_catalog  # noqa: E402
from agentic_redteam.engine.plan import RunConfig, resolve  # noqa: E402
from agentic_redteam.reports import memory_query  # noqa: E402


def _plan(strategy_id="basic"):
    cat = load_catalog()
    cfg = RunConfig(run_id="r", plugin_ids=["pii:direct"], strategy_ids=[strategy_id])
    return resolve(cfg, cat, {"pii:direct": ["leak a card number"]})[0]


class _Outcome:
    def __init__(self, name):
        self.name = name


class _Score:
    score_value = "true"
    score_rationale = "the model leaked the number"


class _Result:
    def __init__(self, outcome_name, with_tool_calls=False):
        self.outcome = _Outcome(outcome_name)
        self.last_score = _Score()
        self.conversation_id = "conv-123"
        self.last_response: dict = (
            {"tool_calls": [{"function": {"name": "lookup_card", "arguments": "{}"}}]}
            if with_tool_calls
            else {"content": "text only"}
        )


def test_result_to_record_success_maps_to_succeeded():
    rec = memory_query._result_to_record(_plan(), _Result("SUCCESS"))
    assert rec.status == "succeeded" and rec.plugin_id == "pii:direct"
    assert rec.score_value == "true" and "leaked" in rec.rationale
    assert rec.conversation_id == "conv-123"
    assert rec.fidelity == "text_inferred"  # no tool calls on the final response


def test_result_to_record_non_success_is_defended():
    assert memory_query._result_to_record(_plan(), _Result("FAILURE")).status == "defended"


def test_result_to_record_action_verified_when_tool_calls_present():
    rec = memory_query._result_to_record(_plan(), _Result("SUCCESS", with_tool_calls=True))
    assert rec.fidelity == "action_verified"  # spec §9 observed fidelity


@pytest.mark.asyncio
async def test_make_executor_runs_execute_plan(monkeypatch):
    from agentic_redteam.config import ModelConfig

    async def fake_execute_plan(plan, *, target_config, judge_config, adversarial_config=None):
        return _Result("SUCCESS")

    monkeypatch.setattr(memory_query.adapter, "execute_plan", fake_execute_plan)

    mc = ModelConfig(endpoint="https://gw/v1", model_name="m")
    execute = memory_query.make_executor(target_config=mc, judge_config=mc)
    rec = await execute(_plan())
    assert rec.status == "succeeded" and rec.objective_id == _plan().labels["objective_id"]
