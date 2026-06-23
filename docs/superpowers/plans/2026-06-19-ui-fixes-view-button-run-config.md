# UI Fixes: View Button Visibility + Run Configuration in Report

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two UI bugs: (1) the "View" button on the run list is nearly invisible and the "View Full Report" button is missing for failed runs; (2) the report page doesn't show what was configured for the run.

**Architecture:** Both fixes are isolated to the web layer — template HTML and one route function. No engine/store schema changes. The run configuration is already persisted as `request_json` in the store; the report route just needs to parse and forward it to the template.

**Tech Stack:** Jinja2 templates, Tailwind CSS (utility classes), FastAPI route in `agentic_redteam/web/routes/runs.py`, Pydantic model `RunRequest`.

---

## File Map

| File | Change |
|------|--------|
| `agentic_redteam/web/templates/runs.html` | Make "View" link always visible (not just on hover) |
| `agentic_redteam/web/templates/live.html` | Show "View Full Report" banner for `failed` runs too |
| `agentic_redteam/web/routes/runs.py` | Parse `request_json` and pass `run_config` dict to report template |
| `agentic_redteam/web/templates/report.html` | Add "Run Configuration" section using `run_config` |
| `tests/web/test_report_route.py` | New: verify `run_config` reaches the report template context |

---

## Task 1: Fix "View" button visibility in run list (`runs.html`)

**Root cause:** The "View →" link in `runs.html` line 70 uses `text-gray-600`, which is nearly invisible on the dark background. It only lightens on `group-hover`. Users miss it.

**Files:**
- Modify: `agentic_redteam/web/templates/runs.html:70`

- [ ] **Step 1: Change the link's default color to always-visible gray**

In `agentic_redteam/web/templates/runs.html`, find line 70 and replace the class string:

```html
<!-- BEFORE -->
<a href="/runs/{{ r.run_id }}"
   class="text-xs text-gray-600 hover:text-red-400 font-semibold transition-colors group-hover:text-gray-300 inline-flex items-center gap-1">
  View <span class="group-hover:translate-x-0.5 transition-transform inline-block">→</span>
</a>

<!-- AFTER -->
<a href="/runs/{{ r.run_id }}"
   class="text-xs text-gray-400 hover:text-red-400 font-semibold transition-colors inline-flex items-center gap-1">
  View <span class="group-hover:translate-x-0.5 transition-transform inline-block">→</span>
</a>
```

- [ ] **Step 2: Verify visually**

Start the app and open the run list at `http://localhost:8000/runs`. The "View" text should be legible on every row without needing to hover. Hovering should turn it red.

- [ ] **Step 3: Commit**

```bash
git add agentic_redteam/web/templates/runs.html
git commit -m "fix: make View link always visible in run list"
```

---

## Task 2: Show "View Full Report" banner for failed runs (`live.html`)

**Root cause:** `live.html` line 89 only shows the "View Full Report" banner when `status in ('completed', 'stopped')`. A `failed` run shows neither the Stop button nor the View button — the user is left with no action.

**Files:**
- Modify: `agentic_redteam/web/templates/live.html:89`

- [ ] **Step 1: Add `'failed'` to the banner condition**

In `agentic_redteam/web/templates/live.html`, find line 89 and change the condition:

```html
<!-- BEFORE -->
{% if ctx.summary.status in ('completed', 'stopped') %}

<!-- AFTER -->
{% if ctx.summary.status in ('completed', 'stopped', 'failed') %}
```

- [ ] **Step 2: Verify visually**

Navigate to a failed run's live page (e.g. `/runs/run_XXXXX`). The "View Full Report →" banner should appear. For a still-running run, the banner should NOT appear (only the Stop button).

- [ ] **Step 3: Commit**

```bash
git add agentic_redteam/web/templates/live.html
git commit -m "fix: show View Full Report banner for failed runs"
```

---

## Task 3: Parse run configuration in the report route (`runs.py`)

**Root cause:** The `run_report` route loads `summary` and `records` but discards `request_json` from the DB row. The configuration (target/attacker/judge endpoints, plugins, strategies) is stored but never forwarded to the template.

**Files:**
- Modify: `agentic_redteam/web/routes/runs.py:118-135`

- [ ] **Step 1: Write a failing test for the new behaviour**

Create `tests/web/test_report_route.py`:

```python
"""Tests that the report route passes run_config to the template."""
import json
import pytest
from unittest.mock import AsyncMock, patch

from agentic_redteam.records import RunRequest, RunSummary
from agentic_redteam.config import ModelConfig
from agentic_redteam.engine.plan import RunConfig
from agentic_redteam.engine.profile import AppProfile


def _make_request_json() -> str:
    req = RunRequest(
        config=RunConfig(
            run_id="run_test01",
            plugin_ids=["pi_jailbreak"],
            strategy_ids=["basic"],
            profile=AppProfile(),
            n=3,
            policy_text="",
        ),
        target=ModelConfig(endpoint="http://target:8000", model_name="gpt-4"),
        judge=ModelConfig(endpoint="http://judge:8000", model_name="gpt-4"),
        adversarial=ModelConfig(endpoint="http://attacker:8001", model_name="llama3"),
        concurrency=2,
        requested_by="tester",
    )
    return req.model_dump_json()


def test_run_config_extracted_from_request_json():
    """_extract_run_config should parse request_json into a display dict."""
    from agentic_redteam.web.routes.runs import _extract_run_config

    cfg = _extract_run_config(_make_request_json())
    assert cfg["target_endpoint"] == "http://target:8000"
    assert cfg["target_model"] == "gpt-4"
    assert cfg["adversarial_endpoint"] == "http://attacker:8001"
    assert cfg["adversarial_model"] == "llama3"
    assert cfg["judge_endpoint"] == "http://judge:8000"
    assert cfg["judge_model"] == "gpt-4"
    assert cfg["plugin_ids"] == ["pi_jailbreak"]
    assert cfg["strategy_ids"] == ["basic"]
    assert cfg["n"] == 3
    assert cfg["concurrency"] == 2
    assert cfg["requested_by"] == "tester"


def test_run_config_returns_none_for_missing_json():
    from agentic_redteam.web.routes.runs import _extract_run_config

    assert _extract_run_config(None) is None
    assert _extract_run_config("") is None
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/web/test_report_route.py -v
```

Expected: `ImportError` or `AttributeError` — `_extract_run_config` doesn't exist yet.

- [ ] **Step 3: Add `_extract_run_config` helper and wire it into the route**

In `agentic_redteam/web/routes/runs.py`, add the helper and update `run_report`:

```python
# Add this helper near the top of the file (after imports):
def _extract_run_config(request_json: str | None) -> dict | None:
    if not request_json:
        return None
    try:
        req = RunRequest.model_validate_json(request_json)
    except Exception:
        return None
    return {
        "target_endpoint": req.target.endpoint,
        "target_model": req.target.model_name,
        "adversarial_endpoint": req.adversarial.endpoint if req.adversarial else None,
        "adversarial_model": req.adversarial.model_name if req.adversarial else None,
        "judge_endpoint": req.judge.endpoint,
        "judge_model": req.judge.model_name,
        "plugin_ids": req.config.plugin_ids,
        "strategy_ids": req.config.strategy_ids,
        "n": req.config.n,
        "concurrency": req.concurrency,
        "requested_by": req.requested_by,
        "policy_text": req.config.policy_text,
    }
```

Then update the `run_report` route (currently lines 118-135) to pass `run_config`:

```python
@router.get("/{run_id}/report")
async def run_report(
    run_id: str,
    request: Request,
    store: Annotated[Store, Depends(get_store)],
) -> HTMLResponse:
    row = await store.get_run(run_id)
    if row and row.get("summary_json") and row["summary_json"] != "{}":
        try:
            summary = RunSummary.model_validate_json(row["summary_json"])
        except Exception:
            summary = RunSummary(run_id=run_id, status=row.get("status", "pending"))
    else:
        summary = RunSummary(run_id=run_id, status=(row["status"] if row else "unknown"))
    records = await store.get_executions(run_id)
    ctx = presenters.report_context(summary, records)
    run_config = _extract_run_config(row.get("request_json") if row else None)
    html = render(
        "report.html",
        title=f"Report — {run_id}",
        ctx=ctx,
        run_config=run_config,
        request=request,
    )
    return HTMLResponse(html)
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/web/test_report_route.py -v
```

Expected: Both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agentic_redteam/web/routes/runs.py tests/web/test_report_route.py
git commit -m "feat: extract run configuration from request_json for report page"
```

---

## Task 4: Add "Run Configuration" section to report template (`report.html`)

**Root cause:** `report.html` has no section showing what was configured for the run. Now that `run_config` is passed from the route, the template just needs to render it.

**Files:**
- Modify: `agentic_redteam/web/templates/report.html`

- [ ] **Step 1: Add a configuration section above the Findings section**

In `agentic_redteam/web/templates/report.html`, insert this block just before line 73 (`<!-- Findings -->`):

```html
  <!-- Run Configuration -->
  {% if run_config %}
  <div class="mb-6">
    <details class="bg-gray-850 border border-gray-800 rounded-xl overflow-hidden">
      <summary class="px-4 py-3.5 cursor-pointer select-none hover:bg-gray-800/50 flex items-center justify-between list-none">
        <h2 class="text-base font-semibold text-gray-200">Run Configuration</h2>
        <span class="text-gray-500 text-xs">▼</span>
      </summary>
      <div class="border-t border-gray-800 px-4 py-4 grid grid-cols-1 gap-4 sm:grid-cols-2">

        <!-- Target -->
        <div>
          <div class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Target LLM</div>
          <div class="text-sm text-gray-200 font-mono">{{ run_config.target_model }}</div>
          <div class="text-xs text-gray-500 mt-0.5 truncate" title="{{ run_config.target_endpoint }}">{{ run_config.target_endpoint }}</div>
        </div>

        <!-- Attacker -->
        {% if run_config.adversarial_endpoint %}
        <div>
          <div class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Attacker LLM</div>
          <div class="text-sm text-gray-200 font-mono">{{ run_config.adversarial_model }}</div>
          <div class="text-xs text-gray-500 mt-0.5 truncate" title="{{ run_config.adversarial_endpoint }}">{{ run_config.adversarial_endpoint }}</div>
        </div>
        {% endif %}

        <!-- Judge -->
        <div>
          <div class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Judge LLM</div>
          <div class="text-sm text-gray-200 font-mono">{{ run_config.judge_model }}</div>
          <div class="text-xs text-gray-500 mt-0.5 truncate" title="{{ run_config.judge_endpoint }}">{{ run_config.judge_endpoint }}</div>
        </div>

        <!-- Plugins -->
        <div>
          <div class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Plugins</div>
          <div class="flex flex-wrap gap-1">
            {% for p in run_config.plugin_ids %}
            <span class="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-300 font-mono">{{ p }}</span>
            {% endfor %}
          </div>
        </div>

        <!-- Strategies -->
        <div>
          <div class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Strategies</div>
          <div class="flex flex-wrap gap-1">
            {% for s in run_config.strategy_ids %}
            <span class="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-300 font-mono">{{ s }}</span>
            {% endfor %}
          </div>
        </div>

        <!-- Run params -->
        <div>
          <div class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Parameters</div>
          <div class="text-xs text-gray-400 space-y-0.5">
            <div>Objectives per plugin: <span class="text-gray-200 font-mono">{{ run_config.n }}</span></div>
            <div>Concurrency: <span class="text-gray-200 font-mono">{{ run_config.concurrency }}</span></div>
            {% if run_config.requested_by %}
            <div>Requested by: <span class="text-gray-200">{{ run_config.requested_by }}</span></div>
            {% endif %}
          </div>
        </div>

        <!-- Policy text -->
        {% if run_config.policy_text %}
        <div class="sm:col-span-2">
          <div class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Policy Text</div>
          <p class="text-xs text-gray-400 bg-gray-900/50 rounded-lg px-3 py-2 border border-gray-800/50 leading-relaxed">{{ run_config.policy_text }}</p>
        </div>
        {% endif %}

      </div>
    </details>
  </div>
  {% endif %}
```

- [ ] **Step 2: Verify visually**

Open any completed run's report at `/runs/<run_id>/report`. A collapsed "Run Configuration" accordion should appear above Findings. Click to expand — it should show target, attacker (if set), judge endpoints/models, plugin tags, strategy tags, and parameters.

For old runs without `request_json` stored, the section should be absent (not break).

- [ ] **Step 3: Commit**

```bash
git add agentic_redteam/web/templates/report.html
git commit -m "feat: show run configuration section in report page"
```

---

## Self-Review

**Spec coverage:**
- Bug 1a (View invisible in list) → Task 1 ✓
- Bug 1b (View missing for failed runs) → Task 2 ✓
- Bug 2 (no config in report) → Tasks 3 + 4 ✓

**Placeholder scan:** None — all steps have concrete code.

**Type consistency:**
- `_extract_run_config` returns `dict | None`; template guards with `{% if run_config %}` ✓
- `run_config` keys used in template match keys set in `_extract_run_config` ✓
- `RunRequest.model_validate_json` is the correct Pydantic v2 API ✓
