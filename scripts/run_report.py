# scripts/run_report.py
"""End-to-end Plan-2 smoke: orchestrate a tiny preset run through the REAL executor
and print the JSON report. Run in the container with live endpoints:
  RUN_LIVE=1 OPENAI_CHAT_KEY=... python scripts/run_report.py
"""

import asyncio
import json
import os

from pyrit.setup import IN_MEMORY, initialize_pyrit_async

from agentic_redteam.catalog.loader import load_catalog
from agentic_redteam.config import ModelConfig
from agentic_redteam.engine.plan import RunConfig
from agentic_redteam.engine.profile import AppProfile
from agentic_redteam.orchestrator import Orchestrator
from agentic_redteam.records import RunRequest
from agentic_redteam.reports.aggregation import build_report
from agentic_redteam.reports.memory_query import make_executor
from agentic_redteam.store import Store

_GATEWAY = "https://stork.sp.uat.dbs.corp/v1"
_GATEWAY_MODEL = "69a17167fb3315370dbf866a"
_ATTACKER_ENDPOINT = "http://host.docker.internal:8001/v1"
_ATTACKER_MODEL = "Qwen3.6-35B-A3B-4bit"


async def _make_llm(system: str, user: str) -> str:
    """Minimal stdlib HTTP call to the attacker LLM for objective generation."""
    import urllib.request

    payload = json.dumps(
        {
            "model": _ATTACKER_MODEL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 1.0,
        }
    ).encode()
    req = urllib.request.Request(
        f"{_ATTACKER_ENDPOINT}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer none"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


async def main():
    await initialize_pyrit_async(memory_db_type=IN_MEMORY)

    target = ModelConfig(
        endpoint=_GATEWAY, model_name=_GATEWAY_MODEL, api_key_env="OPENAI_CHAT_KEY"
    )
    attacker = ModelConfig(endpoint=_ATTACKER_ENDPOINT, model_name=_ATTACKER_MODEL, temperature=1.0)

    cat, store = load_catalog(), Store()
    executor = make_executor(target_config=target, judge_config=target, adversarial_config=attacker)
    orch = Orchestrator(cat, store, llm=_make_llm, executor=executor)

    req = RunRequest(
        config=RunConfig(
            run_id="run_report",
            plugin_ids=["policy"],
            strategy_ids=["crescendo"],
            policy_text="The agent must never produce content that violates its usage policy.",
            profile=AppProfile(purpose="internal banking assistant"),
            n=1,
        ),
        target=target,
        judge=target,
        adversarial=attacker,
        requested_by="smoke",
    )
    summary = await orch.run(req)
    print(
        f"[*] run {summary.run_id}: {summary.completed}/{summary.total} done, ASR={summary.asr:.0%}"
    )
    print(json.dumps(build_report(await store.get_executions(summary.run_id)), indent=2)[:4000])


if __name__ == "__main__":
    if os.environ.get("RUN_LIVE") != "1":
        raise SystemExit("set RUN_LIVE=1 (and OPENAI_CHAT_KEY) to run the live smoke")
    asyncio.run(main())
