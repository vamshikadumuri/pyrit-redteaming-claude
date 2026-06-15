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

**Linux / macOS:**
```bash
docker run -d \
  --name pyrit-redteam \
  -p 8006:8006 \
  -v "$(pwd):/workspace" \
  --env-file .env \
  -e APP_DB=/workspace/app.sqlite3 \
  --entrypoint bash \
  ghcr.io/vamshikadumuri/pyrit:0.14.0-v1 \
  -c "uv pip install -q aiosqlite python-multipart && cd /workspace && PYTHONPATH=/workspace /opt/venv/bin/python scripts/serve.py"
```

**Windows (PowerShell):**
```powershell
docker run -d `
  --name pyrit-redteam `
  -p 8006:8006 `
  -v "${PWD}:/workspace" `
  --env-file .env `
  -e APP_DB=/workspace/app.sqlite3 `
  --entrypoint bash `
  ghcr.io/vamshikadumuri/pyrit:0.14.0-v1 `
  -c "uv pip install -q aiosqlite python-multipart && cd /workspace && PYTHONPATH=/workspace /opt/venv/bin/python scripts/serve.py"
```

Then open **http://localhost:8006** in your browser.

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

```bash
pytest -q
```

Expected: ~143 passed, 1 skipped (PyRIT-only scorer tests skip without the container)

### Inside the container

```bash
docker exec pyrit-redteam bash -c \
  "cd /workspace && PYTHONPATH=/workspace /opt/venv/bin/python -m pytest -q \
   --ignore=tests/web/test_demo.py"
```

---

## How Docker Startup Works

The image `ghcr.io/vamshikadumuri/pyrit:0.14.0-v1` provides PyRIT 0.14.0 in `/opt/venv`. Our code is mounted from the host at `/workspace`. The `-c` command installs the two missing dependencies (`aiosqlite`, `python-multipart`) via the image's built-in `uv` package manager at startup, then launches the web server.

No image rebuild is needed — changes to your local code are live immediately via the volume mount.

---

## Attribution & Licensing

- **promptfoo catalog** — MIT License (v0.121.13, commit 4a33ebc)
- **PyRIT** — Apache 2.0 License (Microsoft)
- **htmx** — Zero-Clause BSD
- **Alpine.js** — MIT License
- **This project** — See LICENSE file
