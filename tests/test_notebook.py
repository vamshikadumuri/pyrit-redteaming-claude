# tests/test_notebook.py
"""Smoke tests for notebooks/pyrit_redteam_poc.ipynb (Plan 4)."""

import json
import uuid
from pathlib import Path

import pytest

_NB = Path(__file__).parent.parent / "notebooks" / "pyrit_redteam_poc.ipynb"


def test_notebook_valid_json():
    assert _NB.exists(), f"notebook not found: {_NB}"
    data = json.loads(_NB.read_text(encoding="utf-8"))
    assert data["nbformat"] == 4
    assert data["cells"]


def test_notebook_has_examples():
    data = json.loads(_NB.read_text(encoding="utf-8"))
    source = "\n".join("".join(c["source"]) for c in data["cells"])
    assert "Example A" in source
    assert "Example B" in source
    assert "Example C" in source


@pytest.mark.asyncio
async def test_notebook_demo_flow():
    """Runs Example A's logic programmatically via demo factories.

    Validates the exact import chain the notebook uses:
    catalog -> RunConfig -> Orchestrator(demo) -> store -> build_report.
    """
    from agentic_redteam.catalog.loader import load_catalog
    from agentic_redteam.config import ModelConfig
    from agentic_redteam.engine.plan import RunConfig
    from agentic_redteam.engine.profile import AppProfile
    from agentic_redteam.orchestrator import Orchestrator
    from agentic_redteam.records import RunRequest
    from agentic_redteam.reports.aggregation import build_report
    from agentic_redteam.store import Store
    from agentic_redteam.web.demo import demo_executor_factory, demo_llm_factory

    catalog = load_catalog()
    preset = catalog.presets["owasp_agentic"]
    run_id = f"nb-test-{uuid.uuid4().hex[:6]}"
    fake = ModelConfig(endpoint="http://fake/v1", model_name="fake")
    config = RunConfig(
        run_id=run_id,
        plugin_ids=preset.plugins[:3],
        attack_class_names=["PromptSendingAttack"],
        profile=AppProfile(purpose="banking chatbot"),
        n=2,
    )
    request = RunRequest(config=config, target=fake, judge=fake, requested_by="nb-test")
    store = Store(":memory:")
    orch = Orchestrator(
        catalog,
        store,
        llm=demo_llm_factory(request),
        executor=demo_executor_factory(request),
    )
    summary = await orch.run(request)

    assert summary.status == "completed"
    records = await store.get_executions(run_id)
    assert len(records) > 0

    report = build_report(records)
    assert report["total_executions"] > 0
    assert 0.0 <= report["overall_asr"] <= 1.0
    run_row = await store.get_run(run_id)
    assert run_row is not None
    assert run_row["status"] == "completed"
