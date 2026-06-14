# PyRIT AI Red-Teaming POC

A self-service web application and Jupyter notebook for red-teaming agentic AI systems using **PyRIT** (Python Risk Identification Toolkit) with **promptfoo's** curated attack taxonomy.

## What This Is

This POC combines:
- **promptfoo catalog** (v0.121.13, commit 4a33ebc) — curated attack taxonomy, objectives, seed hints, and grading rubrics
- **PyRIT engine** — orchestrates multi-turn adversarial attacks
- **Web app** — self-service attack runner with run history and memory query UI
- **Jupyter notebook** — exploratory red-teaming environment

Perfect for testing whether your LLM-powered app can withstand prompt injection, jailbreaks, and other adversarial inputs.

---

## Quick Start (Web App)

```bash
docker run --rm \
  -e PYTHONPATH=/work \
  -e OPENAI_CHAT_KEY="<your-key>" \
  -e ATTACKER_ENDPOINT="http://host.docker.internal:8001/v1" \
  -e ATTACKER_MODEL="local-llm" \
  -p 8006:8006 \
  -v "$(pwd):/work" \
  -w /work \
  ghcr.io/vamshikadumuri/pyrit:0.13.0-v2 \
  scripts/serve.py
```

Then open **http://localhost:8006** in your browser.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_DB` | No | `app.sqlite3` | SQLite database path for run history |
| `PORT` | No | `8006` | Web server port |
| `OPENAI_CHAT_KEY` | Live only | — | API key for target/judge gateway |
| `ATTACKER_ENDPOINT` | Live only | — | vLLM attacker endpoint (e.g. `http://host.docker.internal:8001/v1`) |
| `ATTACKER_MODEL` | Live only | — | Attacker model name (e.g. `llama2-7b`) |

---

## Running Tests

### On Your Laptop
(Pure modules only — no Docker or external dependencies)

```bash
pyritpocvenv\Scripts\python.exe -m pytest -q
```

Expected result: **124 passed, 4 skipped**

The 4 skipped tests require packages only available inside the container:

| Skipped module | Reason | What it tests |
|---|---|---|
| `tests/engine/test_adapter.py` | needs `pyrit` | PyRIT attack class wiring, `build_target`, `build_attack` |
| `tests/engine/test_scorer.py` | needs `pyrit` | polarity inversion, scorer routing, `InsecureCodeScorer` |
| `tests/reports/test_memory_query.py` | needs `pyrit` | `_result_to_record`, `make_executor` |
| `tests/web/test_app.py` | needs `fastapi` | FastAPI wizard/SSE/report routes (6 e2e tests) |

### In Container
(Full suite — adds PyRIT adapter + FastAPI e2e tests)

```bash
docker run --rm --entrypoint python \
  -e PYTHONPATH=/work \
  -v "$(pwd):/work" \
  -w /work \
  ghcr.io/vamshikadumuri/pyrit:0.13.0-v2 \
  -m pytest -q
```

Expected result: **138 passed, 1 skipped** (1 skip = live-endpoint smoke test, gated by `RUN_LIVE=1`)

---

## Architecture

- **Pure modules** (`presenters.py`, `render.py`, `manager.py`) — testable on laptop without external dependencies
- **Web layer** (`app.py`) — FastAPI + SQLite; runs in container only
- **PyRIT integration** (`engine/adapter.py`, `reports/memory_query.py`) — isolated to specific modules for easy substitution
- **Frontend** — htmx 2.0.4 + Alpine.js 3.14.9 + Tailwind CSS (committed to `web/static/`); see below

### Frontend

The web UI uses **htmx 2.0.4 + Alpine.js 3.14.9 + Tailwind CSS Play CDN** (all committed to `agentic_redteam/web/static/` — no external CDN required). Dark Pro theme across all pages. The wizard uses htmx partial swaps; the live run view uses htmx-ext-sse for streaming execution events.

---

## Volumes & Paths

The repository is mounted at `/work` inside the container. PyRIT runs inside the container and loads our package via `PYTHONPATH=/work`, so no `pip install` is needed—changes to your local repo are immediately visible in the container.

Run history and memory are persisted to `app.sqlite3` (or the path specified by `APP_DB`), which is also accessible from your host via the volume mount.

---

## Known Issues (Container Carry-Forwards)

These are open unverified items that only manifest inside the container against real PyRIT 0.13.0-v2:

| # | Where | Issue | Workaround |
|---|---|---|---|
| B2 | `reports/memory_query.py` | `AttackResult` field names (`outcome`, `last_score`, `last_response`) not confirmed — uses `getattr` fallbacks | Tolerant fallbacks degrade gracefully; records may show blank rationale if names changed |
| B3 | `reports/memory_query.py::records_from_memory` | Raises `NotImplementedError` — `CentralMemory` label-query API unconfirmed | Live reports read from SQLite store (not PyRIT memory) — reporting works; re-open-past-run path disabled |
| B4 | `engine/adapter.py::execute_plan` | `memory_labels=` kwarg on `execute_async` wrapped in try/except — unknown which branch runs | Falls back to calling without labels; memory label queries may not work |
| B5 | `engine/adapter.py::_build_converters` | `request_converter_configurations=` attachment on `PromptSendingAttack` not verified | Converter strategies (e.g. `leetspeak`) not exercised in Crescendo path; may silently fail |

**Live view stats cards**: The Alpine.js `@htmx:sseMessage.window` listener in `live.html` should increment counters correctly — verify in the browser during an active run. If counters stay at 0, confirm htmx-ext-sse is dispatching the `htmx:sseMessage` event with `detail.type === 'execution_done'`.

---

## Attribution & Licensing

- **promptfoo catalog** — MIT License (v0.121.13, commit 4a33ebc); taxonomy, attack descriptions, seed hints, and grading rubrics reused as static corpus from `promptfoo_plugins_catalog_1.xlsx`
- **PyRIT** — Apache 2.0 License
- **This POC** — See LICENSE file in repository root
