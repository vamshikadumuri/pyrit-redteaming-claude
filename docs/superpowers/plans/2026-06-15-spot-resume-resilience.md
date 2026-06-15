# Plan: Spot-preemption-resilient runs with scheduled auto-resume

## Context

The attacker LLM (per `2026-06-15-costing-dolphinx1405b.md`) is intended to run on a **spot/preemptible GPU instance** to cut cost ~50%. Spot instances can be reclaimed at any moment, which takes the attacker endpoint offline mid-scan. Today that loses work:

- **During objective generation** (`live.py:_llm` → `sourcing._generate`): no try/except, no retry. If the endpoint is down, the exception bubbles up and `RunManager` marks the whole run `failed` (`manager.py:58-66`). **Objectives are LLM-generated and never persisted**, so there is nothing to resume to.
- **During per-plan execution** (`adapter.execute_plan`): each failure is caught (`orchestrator.py:98-101`), saved as an `error` record, and the run **continues to the end as `completed`** — so a long outage produces a run full of `error` rows that are never retried.
- **"Re-run"** (`runs.py:90-104`) starts a brand-new run with a new `run_id` and **re-sources objectives from scratch** — it is a fresh scan, not a resume.

What already works in our favor: the unit of work is one `(plugin, strategy, objective)` = one `AttackPlan` = one `executions` row, written **incrementally** the instant it completes via `INSERT OR REPLACE` on PK `(run_id, plugin_id, strategy_id, objective_id)` (`store.py:38,136-150`). So completed units already survive a crash — we just never read them back to skip.

**Goal:** when the attacker (or target) endpoint goes down, the run is paused (not lost), all completed units are preserved, and a scheduled checker auto-resumes the run from the last point of progress once the endpoint is reachable again — retried *later when the spot instance is back*, not via tight immediate backoff. Works uniformly across all plugin × strategy combinations (the unit granularity is already per-combo, so nothing combo-specific is needed).

## Design

Introduce a new run status **`interrupted`** = "hit an endpoint outage, has remaining work, eligible for scheduled resume" — distinct from `failed` (genuine non-retryable), `completed` (plan finished), `stopped` (user cancelled).

Three pieces:

1. **Resume = skip-completed re-execution under the same `run_id`.** Persist the resolved objectives once at run start so resume reconstructs the *exact same* plan set deterministically (`resolve()` is pure). The resume predicate: **run every plan that does not already have a `succeeded` or `defended` record.** This naturally covers never-started plans (no row), `error` rows (retried), and crash-mid-run. No new per-item `pending`/`running` state needed.

2. **Endpoint-down classification + circuit-break.** Treat connection errors / timeouts / 5xx / 429 from the attacker or target endpoint as "endpoint down" (`httpx.ConnectError`, `ConnectTimeout`, `ReadTimeout`, `HTTPStatusError` 5xx/429). On detecting it: stop launching new plans (reuse the existing cancel mechanism) and finish the run as `interrupted` rather than `completed`/`failed`. A down endpoint during the sourcing phase → `interrupted` with zero progress (nothing lost, retry sourcing later).

3. **Scheduled auto-resume (the "cron").** An in-process periodic asyncio task started in the FastAPI `_lifespan` (`app.py:36-50`). Every N minutes it finds `interrupted` runs, health-checks each run's attacker endpoint (`GET {endpoint}/models`), and calls `manager.resume(run_id)` for the healthy ones. In-process is chosen because the app is a long-running service — it needs no external scheduler and directly matches "retry later when the spot instance is available." A manual `POST /runs/{run_id}/resume` endpoint is also added (immediate trigger + testability), plus `POST /runs/resume-pending` so an external cron/k8s CronJob can drive it instead if desired. Interval + enable flag come from env vars (default on, e.g. 5 min).

Design note: per the spot-instance use case, we deliberately do **not** add tight exponential-backoff retry to the LLM call sites — recovery may be minutes-to-hours away (until the spot instance is rescheduled), so the periodic scheduler is the retry mechanism, not in-call backoff.

## Changes by file

**`agentic_redteam/store.py`**
- Add additive column `objectives_json TEXT NOT NULL DEFAULT '{}'` to `runs`, with an `ALTER TABLE ... ADD COLUMN` migration mirroring the existing `request_json` migration (`store.py:66-69`).
- `save_objectives(run_id, objectives_by_plugin)` and include it in `get_run`'s dict (already `SELECT *`).
- `list_runs_by_status(status)` (or filter `list_runs()` in the scheduler — pick the smaller change).

**`agentic_redteam/orchestrator.py`** (`run()`, `_one()`)
- Add `resume: bool = False` to `run()`. On resume: load persisted `objectives_by_plugin` from the store instead of calling `source_objectives` (skips the gen LLM entirely); re-`resolve()`; load existing executions and build a `done` set of keys with status in `{succeeded, defended}`; skip plans already in `done`.
- On a fresh run, persist objectives via `store.save_objectives(...)` right after sourcing (before the execution loop).
- Wrap sourcing so an endpoint-down error → finish as `interrupted` (not an uncaught raise).
- In `_one()`: classify the caught exception; if endpoint-down, set an `self._interrupted` flag and short-circuit remaining plans (reuse the `_cancelled` pattern, `orchestrator.py:49-51,93-97`). Final status: `interrupted` if the flag is set, else existing `stopped`/`completed`.
- Helper `_is_endpoint_down(exc) -> bool` (httpx exception types) — keep it small and local, or in a tiny `engine/resilience.py` shared with the gen path.

**`agentic_redteam/web/manager.py`**
- `resume(run_id)`: load `request_json` → `RunRequest`, build the Orchestrator, launch `orch.run(request, resume=True)` (same `run_id`).
- In `_run_with_error_handling` (`manager.py:58-66`): map endpoint-down to status `interrupted`; keep `failed` only for genuine non-retryable exceptions.

**`agentic_redteam/web/scheduler.py`** (new)
- `ResumeScheduler` with an asyncio loop: every interval, `store` → `interrupted` runs → health-check attacker endpoint (cheap `GET {endpoint}/models` via httpx, short timeout) → `manager.resume(run_id)` for healthy ones. Started/stopped in `app.py` `_lifespan`. Env: `RESUME_SCHEDULER_ENABLED` (default true), `RESUME_SCHEDULER_INTERVAL_SEC` (default 300).

**`agentic_redteam/web/routes/runs.py`**
- `POST /runs/{run_id}/resume` → `manager.resume(run_id)` (mirrors `rerun_run`, redirects to `/runs/{run_id}`).
- `POST /runs/resume-pending` → resume all currently-healthy `interrupted` runs (for external cron).

**`agentic_redteam/web/app.py`**
- In `_lifespan`, construct and start `ResumeScheduler` after the manager is wired; cancel it in the `finally`.

**`agentic_redteam/records.py`**
- Update the `RunSummary.status` docstring (`records.py:101`) to include `interrupted`. (No new fields required.)

**Templates** (`templates/runs.html`, `live.html`) — render `interrupted` status (amber) and show a "Resume" button next to "Re-run" for interrupted runs. Cosmetic; mirror existing status styling (`runs.html:41`, `live.html:13`).

## Reuse notes (don't reinvent)
- Skip-completed keying already exists: composite PK + `INSERT OR REPLACE` (`store.py:38,139`) and `get_executions(run_id)` (`store.py:152`).
- Circuit-break uses the existing cancel pattern (`orchestrator.py:49-51,93-97`), not new machinery.
- Resume reuses `request_json` reconstruction exactly as `rerun_run` already does (`runs.py:99`).
- `resolve()` is pure and deterministic given the same objectives (`plan.py:66-108`) — this is why persisting objectives is sufficient for an identical plan set.

## Phasing
1. **Persist objectives + resume core** → verify: orchestrator unit test (fake executor) that fails part-way, asserts partial executions persisted, then `run(resume=True)` skips completed units and finishes `completed` with identical objectives.
2. **Endpoint-down classification + `interrupted` status** → verify: fake executor raising `httpx.ConnectError` flips the run to `interrupted` and stops launching remaining plans.
3. **Manual resume endpoint** → verify: `tests/web/test_manager.py` / app test drives `POST /runs/{id}/resume` and observes completion.
4. **Scheduler** → verify: scheduler test with a fake health-check that returns down-then-up; assert it resumes the interrupted run only once healthy.

## Verification (end-to-end)
- Extend existing laptop-testable suites (injected fake executor/llm, no PyRIT): `tests/test_orchestrator.py`, `tests/test_store.py`, `tests/web/test_manager.py`, `tests/test_pipeline_integration.py`, plus a new `tests/web/test_scheduler.py`.
- Run `pytest` green; `ruff`/`ruff-format`/`mypy` (pre-commit hooks) clean.
- Manual smoke in the container: start a run, kill the attacker endpoint mid-scan → run becomes `interrupted` with partial results; bring the endpoint back → within one scheduler interval the run resumes and completes with no duplicated or lost units.

## Open decision (recommended default chosen)
- Scheduler is **in-process** (recommended, self-contained). The `POST /runs/resume-pending` endpoint is included so an external cron/k8s CronJob can be used instead without code changes.
