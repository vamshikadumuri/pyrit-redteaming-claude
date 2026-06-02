# tests/test_progress.py
import asyncio

import pytest

from agentic_redteam.progress import ProgressBus, ProgressEvent


@pytest.mark.asyncio
async def test_published_events_reach_a_subscriber():
    bus = ProgressBus()
    q = bus.subscribe()
    await bus.publish(ProgressEvent(run_id="r", kind="run_started", total=3))
    await bus.publish(ProgressEvent(run_id="r", kind="execution_done", completed=1, total=3,
                                    plugin_id="pii:direct", status="defended"))
    first = await asyncio.wait_for(q.get(), timeout=1)
    second = await asyncio.wait_for(q.get(), timeout=1)
    assert first.kind == "run_started" and second.completed == 1


@pytest.mark.asyncio
async def test_fan_out_to_multiple_subscribers():
    bus = ProgressBus()
    a, b = bus.subscribe(), bus.subscribe()
    await bus.publish(ProgressEvent(run_id="r", kind="run_finished", completed=3, total=3))
    assert (await asyncio.wait_for(a.get(), timeout=1)).kind == "run_finished"
    assert (await asyncio.wait_for(b.get(), timeout=1)).kind == "run_finished"
