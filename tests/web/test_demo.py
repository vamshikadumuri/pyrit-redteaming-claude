import asyncio
import json

from agentic_redteam.catalog.loader import load_catalog
from agentic_redteam.engine.plan import RunConfig, resolve
from agentic_redteam.web import demo


def test_demo_executor_is_deterministic_and_records_status():
    cat = load_catalog()
    cfg = RunConfig(
        run_id="r1", plugin_ids=["pii:direct"], attack_class_names=["PromptSendingAttack"], n=1
    )
    plans = resolve(cfg, cat, {"pii:direct": ["exfiltrate PII"]})
    ex = demo.demo_executor_factory(None)
    r1 = asyncio.run(ex(plans[0]))
    r2 = asyncio.run(ex(plans[0]))
    assert r1.status in ("succeeded", "defended") and r1.status == r2.status
    assert r1.run_id == "r1"


def test_demo_llm_returns_json_array():
    out = asyncio.run(demo.demo_llm_factory(None)("sys", "user"))
    parsed = json.loads(out)
    assert isinstance(parsed, list) and len(parsed) >= 3
