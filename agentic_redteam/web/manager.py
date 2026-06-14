"""RunManager (spec §11): owns the shared ProgressBus + a registry of in-flight runs.
Builds one Orchestrator per run with the executor + generation-LLM derived from that
RunRequest, launches it as an asyncio task, and exposes stop()/wait(). Pure: the
executor_factory + llm_factory are injected (demo or live), so the run lifecycle is
laptop-testable without PyRIT."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from agentic_redteam.catalog.loader import Catalog
from agentic_redteam.engine.generate import LLMCallable
from agentic_redteam.orchestrator import Executor, Orchestrator
from agentic_redteam.progress import ProgressBus, ProgressEvent
from agentic_redteam.records import RunRequest
from agentic_redteam.store import Store

_log = logging.getLogger(__name__)

ExecutorFactory = Callable[[RunRequest], Executor]
LLMFactory = Callable[[RunRequest], LLMCallable]


class RunManager:
    def __init__(
        self,
        catalog: Catalog,
        store: Store,
        *,
        executor_factory: ExecutorFactory,
        llm_factory: LLMFactory,
        bus: ProgressBus | None = None,
    ):
        self._catalog = catalog
        self._store = store
        self._executor_factory = executor_factory
        self._llm_factory = llm_factory
        self._bus = bus or ProgressBus()
        self._runs: dict[str, tuple[Orchestrator, asyncio.Task]] = {}

    @property
    def bus(self) -> ProgressBus:
        return self._bus

    def start(self, request: RunRequest) -> str:
        """Launch a run as an asyncio background task. Returns the run_id."""
        run_id = request.config.run_id
        orch = Orchestrator(
            self._catalog,
            self._store,
            llm=self._llm_factory(request),
            executor=self._executor_factory(request),
            bus=self._bus,
        )

        async def _run_with_error_handling():
            try:
                return await orch.run(request)
            except Exception as exc:
                _log.error("Run %s failed: %s", run_id, exc, exc_info=True)
                await self._store.set_status(run_id, "failed")
                await self._bus.publish(ProgressEvent(
                    run_id=run_id, kind="run_finished", completed=0, total=0))

        task = asyncio.create_task(_run_with_error_handling())
        self._runs[run_id] = (orch, task)
        return run_id

    def stop(self, run_id: str) -> None:
        """Signal the orchestrator to stop a run."""
        run = self._runs.get(run_id)
        if run:
            run[0].stop(run_id)

    async def wait(self, run_id: str) -> None:
        """Await the run's asyncio task (for tests and graceful shutdown)."""
        run = self._runs.get(run_id)
        if run:
            await run[1]
