"""Live (real) executor + generation-LLM factories — the PyRIT boundary for the web
app (mirrors scripts/run_report.py). Imports are lazy so this module imports fine on a
laptop; calling a factory needs the pyrit:0.13.0-v2 container + reachable endpoints."""
from __future__ import annotations

import os

from agentic_redteam.records import RunRequest


def real_executor_factory(request: RunRequest):
    """Build the live PyRIT executor for a run. Lazy import: PyRIT is only needed
    inside the container."""
    from agentic_redteam.reports.memory_query import make_executor  # PyRIT import
    return make_executor(
        target_config=request.target,
        judge_config=request.judge,
        adversarial_config=request.adversarial,
    )


def real_llm_factory(request: RunRequest):
    """Build the generation-LLM callable from the run's adversarial config.
    Falls back to the target config if no adversarial LLM is provided (e.g. basic strategy)."""
    gen_config = request.adversarial or request.target
    endpoint = gen_config.endpoint.rstrip("/")
    model = gen_config.model_name
    try:
        api_key = gen_config.resolve_api_key()
    except KeyError:
        api_key = "none"

    async def _llm(system: str, user: str) -> str:
        import httpx  # available in the pyrit:0.13.0-v2 container
        payload = {
            "model": model,
            "temperature": 1.0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{endpoint}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]

    return _llm
