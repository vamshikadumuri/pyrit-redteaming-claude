# agentic_redteam/orchestrator.py
"""Async run orchestrator (spec §11). Expands a RunRequest into executions
(source objectives -> resolve -> [AttackPlan]), runs them under a concurrency
semaphore, persists status + records to the Store + an audit entry, and publishes
ProgressEvents. Pure: the per-plan executor is injected (Executor type) so the whole
pipeline is laptop-testable without PyRIT; the container supplies the real executor
via reports.memory_query.make_executor()."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from agentic_redteam.catalog.loader import Catalog
from agentic_redteam.engine.generate import LLMCallable
from agentic_redteam.engine.plan import AttackPlan, resolve
from agentic_redteam.progress import ProgressBus, ProgressEvent
from agentic_redteam.records import ExecutionRecord, RunRequest, RunSummary
from agentic_redteam.sourcing import source_objectives
from agentic_redteam.store import Store

Executor = Callable[[AttackPlan], Awaitable[ExecutionRecord]]


class Orchestrator:
    def __init__(
        self,
        catalog: Catalog,
        store: Store,
        *,
        llm: LLMCallable,
        executor: Executor,
        bus: ProgressBus | None = None,
    ):
        self._catalog = catalog
        self._store = store
        self._llm = llm
        self._executor = executor
        self._bus = bus or ProgressBus()
        self._cancelled: set[str] = set()

    @property
    def bus(self) -> ProgressBus:
        return self._bus

    def stop(self, run_id: str) -> None:
        """Cancel a run: pending executions are skipped; the run ends 'stopped'."""
        self._cancelled.add(run_id)

    async def run(self, request: RunRequest) -> RunSummary:
        cfg = request.config
        await self._store.create_run(request)

        objectives, notes = await source_objectives(
            self._catalog,
            plugin_ids=cfg.plugin_ids,
            profile=cfg.profile,
            llm=self._llm,
            n=cfg.n,
            user_goals=request.user_goals,
            policy_text=cfg.policy_text,
            datasets_dir=request.datasets_dir,
        )
        plans = resolve(cfg, self._catalog, objectives)

        total_objs = sum(len(v) for v in objectives.values())
        await self._store.add_audit(
            run_id=cfg.run_id,
            requested_by=request.requested_by,
            target_endpoint=request.target.endpoint,
            objective_count=total_objs,
            detail="; ".join(f"{k}: {v}" for k, v in notes.items()),
        )

        summary = RunSummary(run_id=cfg.run_id, status="running", total=len(plans))
        await self._store.set_status(cfg.run_id, "running")
        await self._bus.publish(
            ProgressEvent(run_id=cfg.run_id, kind="run_started", completed=0, total=len(plans))
        )

        sem = asyncio.Semaphore(max(1, request.concurrency))

        async def _one(plan: AttackPlan) -> None:
            if cfg.run_id in self._cancelled:
                return
            async with sem:
                if cfg.run_id in self._cancelled:
                    return
                try:
                    record = await self._executor(plan)
                except Exception as e:  # harness failure -> error record; run continues
                    record = ExecutionRecord.from_plan(plan, status="error", error=str(e))
                await self._store.save_execution(record)
                summary.completed += 1
                summary.succeeded += int(record.status == "succeeded")
                summary.errors += int(record.status == "error")
                await self._bus.publish(
                    ProgressEvent(
                        run_id=cfg.run_id,
                        kind="execution_done",
                        completed=summary.completed,
                        total=summary.total,
                        plugin_id=record.plugin_id,
                        strategy_id=record.strategy_id,
                        objective_id=record.objective_id,
                        status=record.status,
                    )
                )

        await asyncio.gather(*[_one(p) for p in plans])

        summary.status = "stopped" if cfg.run_id in self._cancelled else "completed"
        await self._store.save_summary(summary)
        await self._bus.publish(
            ProgressEvent(
                run_id=cfg.run_id,
                kind="run_finished",
                completed=summary.completed,
                total=summary.total,
            )
        )
        return summary
