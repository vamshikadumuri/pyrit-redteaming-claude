# agentic_redteam/progress.py
"""Transport-agnostic progress events (spec §11 live view). The orchestrator
publishes ProgressEvents to a ProgressBus; Plan 3's web layer subscribes and
relays them over SSE. Pure asyncio fan-out — no web/PyRIT dependency."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable

from pydantic import BaseModel


class ProgressEvent(BaseModel):
    run_id: str
    kind: str  # "run_started" | "execution_done" | "run_finished"
    completed: int = 0
    total: int = 0
    plugin_id: str = ""
    strategy_id: str = ""
    objective_id: str = ""
    status: str = ""  # execution status, for kind == "execution_done"


class ProgressBus:
    """Async pub/sub fan-out. subscribe() returns a queue that receives every event
    published after subscription; the web layer drains it for an SSE stream."""

    def __init__(self):
        self._queues: list[asyncio.Queue] = []

    def subscribe(self) -> tuple[asyncio.Queue, Callable[[], None]]:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.append(q)

        def _unsubscribe():
            with contextlib.suppress(ValueError):
                self._queues.remove(q)

        return q, _unsubscribe

    async def publish(self, event: ProgressEvent) -> None:
        for q in self._queues:
            await q.put(event)
