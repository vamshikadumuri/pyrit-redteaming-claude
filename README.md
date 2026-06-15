# PyRIT AI Red-Teaming

A self-service web application and Jupyter notebook for red-teaming agentic AI systems using **PyRIT 0.14.0** with **promptfoo's** curated attack taxonomy.

## What This Is

- **promptfoo catalog** (v0.121.13) — curated attack taxonomy, objectives, and grading rubrics
- **PyRIT 0.14.0 engine** — orchestrates single-turn and multi-turn adversarial attacks (Crescendo, Tree-of-Attacks, etc.)
- **Web app** — self-service attack wizard, live run view, full report with re-run support
- **Jupyter notebook** — exploratory red-teaming environment

---

## Quick Start

### Prerequisites

Create a `.env` file in the project root:

```env
ATTACKER_LLM_ENDPOINT=https://api.openai.com/v1
ATTACKER_LLM_MODEL=gpt-4o-mini
ATTACKER_LLM_API_KEY=sk-...

JUDGE_LLM_ENDPOINT=https://api.openai.com/v1
JUDGE_LLM_MODEL=gpt-4o-mini
JUDGE_LLM_API_KEY=sk-...
```

### Run (Docker)

**Build once** (bakes app dependencies into a derived image — no install at startup):

```bash
docker build -t pyrit-redteam .
```

**Linux / macOS:**
```bash
docker run -d \
  --name pyrit-redteam \
  -p 8006:8006 \
  -v "$(pwd):/workspace" \
  --env-file .env \
  -e APP_DB=/workspace/app.sqlite3 \
  pyrit-redteam
```

**Windows (PowerShell):**
```powershell
docker run -d `
  --name pyrit-redteam `
  -p 8006:8006 `
  -v "${PWD}:/workspace" `
  --env-file .env `
  -e APP_DB=/workspace/app.sqlite3 `
  pyrit-redteam
```

Then open **http://localhost:8006** in your browser.

Your local code is bind-mounted — edits are live without a rebuild. Only re-run `docker build` if `requirements.txt` changes.

**Stop:**
```bash
docker rm -f pyrit-redteam
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_DB` | No | `app.sqlite3` | SQLite path for run history |
| `PORT` | No | `8006` | Web server port |
| `ATTACKER_LLM_ENDPOINT` | Yes | — | OpenAI-compatible attacker LLM endpoint |
| `ATTACKER_LLM_MODEL` | Yes | — | Attacker model name |
| `ATTACKER_LLM_API_KEY` | Yes | — | Attacker LLM API key |
| `JUDGE_LLM_ENDPOINT` | Yes | — | OpenAI-compatible judge LLM endpoint |
| `JUDGE_LLM_MODEL` | Yes | — | Judge model name |
| `JUDGE_LLM_API_KEY` | Yes | — | Judge LLM API key |

Target model endpoint and credentials are configured per-run in the wizard UI (Step 1).

---

## Features

### Run Wizard
6-step wizard: target model → attack plugins → adversarial LLM → judge → app profile → run config. Supports single-turn (`PromptSending`, `RolePlay`) and multi-turn (`Crescendo`, `TreeOfAttacksWithPruning`) strategies.

### Live Run View
Real-time SSE feed showing each execution as it completes. Progress bar, stat cards, stop button.

### Report
- **Summary scorecard** — overall ASR, succeeded / defended / errors
- **Findings accordion** — one card per successful attack with objective, conversation log (multi-turn), scorer verdict, and judge rationale
- **All Executions table** — full transparency log with click-to-expand rows showing conversation, response, and rationale
- **Framework scorecard** — ASR breakdown by OWASP LLM Top 10, OWASP Agentic, OWASP API, MITRE ATLAS
- **Plugin × Strategy heatmap** — ASR grid across all tested combinations
- **Sanity flags** — warns on implausible all-pass / all-fail results
- **JSON export** — download full report as JSON
- **Print** — print-friendly layout

### Re-run
Every completed run stores its full configuration. Hit **↺ Re-run** from the report or live view to instantly launch an identical run with a new ID.

### Conversation Log
For multi-turn attacks (Crescendo, TAP), each execution record captures the full turn-by-turn exchange from PyRIT memory. Shown as a collapsible conversation timeline in the report.

---

## Architecture

```
agentic_redteam/
├── catalog/          # promptfoo plugin + strategy definitions (pure, no PyRIT)
├── engine/
│   ├── adapter.py    # ONLY module importing PyRIT attacks — AttackExecutor API
│   ├── scorer.py     # PromptfooRubricScorer (TrueFalseScorer subclass)
│   ├── plan.py       # AttackPlan, RunConfig (pure data)
│   └── generate.py   # LLM-based objective generation
├── orchestrator.py   # Fan-out: plugins × strategies × objectives → ExecutionRecords
├── store.py          # aiosqlite app store (runs, executions, audit log)
├── records.py        # ExecutionRecord, RunRequest, RunSummary (pure Pydantic)
├── reports/
│   ├── aggregation.py    # Pure: scorecard, heatmap, findings, sanity flags
│   └── memory_query.py   # PyRIT CentralMemory → conversation log population
└── web/
    ├── app.py            # FastAPI app factory + lifespan
    ├── routes/
    │   ├── wizard.py     # GET/POST /wizard steps
    │   └── runs.py       # /runs CRUD + /rerun + SSE events
    ├── templates/        # Jinja2 — htmx 2.0.4 + Alpine.js + Tailwind CSS
    └── static/           # Vendored JS/CSS (no external CDN)
```

**Design principle:** PyRIT is isolated to two modules (`engine/adapter.py`, `reports/memory_query.py`). Everything else is pure Python, testable on the laptop without Docker.

---

## Running Tests

### Laptop (pure modules)

Install dev dependencies into a local venv first:

```bash
pip install -r requirements-dev.txt
pytest -q
```

Expected: ~143 passed, 1 skipped (PyRIT-only scorer tests skip without the container)

### Inside the container

```bash
docker exec pyrit-redteam python -m pytest -q --ignore=tests/web/test_demo.py
```

---

## How the Image is Built

**PyRIT comes from the base image.** `Dockerfile` extends `ghcr.io/vamshikadumuri/pyrit:0.14.0-v1` (which ships PyRIT 0.14.0 in `/opt/venv`) and bakes in the app's remaining dependencies from `requirements.txt` at build time. No packages are installed at container startup.

**App code is bind-mounted**, not baked into the image — edits on the host are live immediately. Only re-run `docker build` when `requirements.txt` changes.

### Migrating to your org's image

When your org provides a UBI-Python base image with PyRIT pre-installed, the migration is a one-line change in `Dockerfile`:

```dockerfile
# Change this line:
ARG BASE_IMAGE=ghcr.io/vamshikadumuri/pyrit:0.14.0-v1

# To your org image, e.g.:
ARG BASE_IMAGE=registry.org.internal/ubi9-python311-pyrit:1.0
```

Also switch the `RUN` line from `uv pip install` to `pip install --no-cache-dir` (UBI images ship standard pip). Nothing in the app code changes.

---

## Attribution & Licensing

- **promptfoo catalog** — MIT License (v0.121.13, commit 4a33ebc)
- **PyRIT** — Apache 2.0 License (Microsoft)
- **htmx** — Zero-Clause BSD
- **Alpine.js** — MIT License
- **This project** — See LICENSE file
