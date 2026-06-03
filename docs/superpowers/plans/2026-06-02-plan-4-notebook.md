# Plan 4 — Jupyter Notebook Parity

**Status:** Ready to execute.  
**Depends on:** Plans 1a, 1b, 1c, 2, 3 (all done).

## Goal

A single notebook `notebooks/pyrit_redteam_poc.ipynb` that demonstrates the full POC  
end-to-end using the **same catalog, engine, orchestrator, store, and report modules as  
the web app** — no reimplementation. One engine, one catalog; web app and notebook never drift.

Spec reference: §15.

---

## Tasks

### Task 1 — `notebooks/pyrit_redteam_poc.ipynb`

Three worked examples, all sharing `load_catalog()`, `Orchestrator`, `Store`, `build_report`:

| Example | Plugin(s) | Strategy | Mode |
|---|---|---|---|
| **A — Preset run** | `owasp_agentic` preset, first 5 | `jailbreak` (preset default) | Demo (no network) |
| **B — Custom Crescendo** | `agentic:indirect-prompt-injection` | `crescendo` | Live (container) / fallback demo |
| **C — Explore results** | all records from Example A | — | read-only store query |

**Example A** — OWASP Agentic preset, demo mode.  
`RunConfig` → `Orchestrator.run()` (demo executor + demo LLM) → `store.get_executions()`  
→ `build_report()` → print scorecard (OWASP Agentic codes, per-plugin ASR bar).

**Example B** — Refactors `crescendo.py` through the engine.  
Configures `RunConfig(plugin_ids=["agentic:indirect-prompt-injection"], strategy_ids=["crescendo"])`.  
Reads `TARGET_ENDPOINT`, `TARGET_MODEL`, `ATTACKER_ENDPOINT`, `ATTACKER_MODEL` env vars.  
Uses `real_executor_factory` + `real_llm_factory` (lazy PyRIT import, container only);  
falls back to demo factories when `DEMO_MODE=1`. Shows per-record fidelity + conversation_id.

**Example C** — Explore results.  
`store.list_runs()`, `store.get_executions(run_id)`, `build_report()`.  
Displays full framework scorecard (all 4 families), findings list (first 5), sanity flags.

**Notebook setup:** path-inserts project root for local runs; `PYTHONPATH=/work` covers container.  
All async cells use top-level `await` (IPykernel ≥ 5.0 / Python 3.11 standard).

---

### Task 2 — `tests/test_notebook.py`

Three tests:

| Test | What it checks |
|---|---|
| `test_notebook_valid_json` | File exists, valid JSON, `nbformat == 4`. |
| `test_notebook_has_examples` | Source text contains "Example A", "Example B", "Example C". |
| `test_notebook_demo_flow` | Runs Example A logic via demo factories; asserts `summary.status == "completed"` and `report["total_executions"] > 0`. |

`test_notebook_demo_flow` exercises the exact same import chain the notebook uses  
(catalog → RunConfig → Orchestrator → demo factories → store → build_report).

---

## Verify

```
pyritpocvenv\Scripts\python.exe -m pytest tests/test_notebook.py -q
```

Expected: **3 passed**.  
Full suite (`-m pytest -q`) should stay green (no regressions).
