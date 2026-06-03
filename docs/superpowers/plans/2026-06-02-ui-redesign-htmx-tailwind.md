# UI Redesign — htmx + Tailwind + Dark Pro Theme — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the vanilla-CSS/JS web UI with a polished Dark Pro theme using htmx 2.x, Alpine.js 3.x, and Tailwind CSS Play CDN — all committed as static files, zero CDN at runtime.

**Architecture:** Static assets (htmx, Alpine, Tailwind Play CDN) downloaded once and committed to `static/`. All 5 templates fully rewritten. Two new FastAPI partial routes (`GET/POST /wizard/step/{n}`) power htmx wizard navigation. SSE generator updated to emit named events with pre-rendered HTML fragments. Alpine.js handles stats counters and wizard step state client-side. No build step required.

**Tech Stack:** FastAPI + Jinja2 (existing), htmx 2.0.4, Alpine.js 3.14.9, Tailwind Play CDN 3.x — all served from `static/`

---

## File Map

**Download / create:**
- `static/htmx.min.js`
- `static/htmx-ext-sse.js`
- `static/alpine.min.js`
- `static/tailwind-cdn.js`

**Rewrite:**
- `agentic_redteam/web/templates/base.html`
- `agentic_redteam/web/templates/wizard.html`
- `agentic_redteam/web/templates/live.html`
- `agentic_redteam/web/templates/report.html`
- `agentic_redteam/web/templates/runs.html`

**Create (partials):**
- `agentic_redteam/web/templates/partials/wizard_step_1.html`
- `agentic_redteam/web/templates/partials/wizard_step_2.html`
- `agentic_redteam/web/templates/partials/wizard_step_3.html`
- `agentic_redteam/web/templates/partials/wizard_step_4.html`
- `agentic_redteam/web/templates/partials/wizard_step_5.html`
- `agentic_redteam/web/templates/partials/wizard_step_6.html`
- `agentic_redteam/web/templates/partials/feed_row.html`
- `agentic_redteam/web/templates/partials/run_finished.html`

**Modify:**
- `agentic_redteam/web/render.py` — accept optional `request` kwarg, inject `current_path` + `demo_mode`
- `agentic_redteam/web/app.py` — add wizard partial routes, update SSE generator, pass `request=request` to all render calls
- `tests/web/test_app.py` — add wizard partial route tests

**Delete:**
- `static/app.css`
- `static/app.js`

---

## Task 1: Download and commit static assets

**Files:**
- Create: `static/htmx.min.js`, `static/htmx-ext-sse.js`, `static/alpine.min.js`, `static/tailwind-cdn.js`

- [ ] **Step 1: Download all four files via PowerShell**

```powershell
Invoke-WebRequest "https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js" -OutFile "static/htmx.min.js"
Invoke-WebRequest "https://unpkg.com/htmx-ext-sse@2.2.2/sse.js" -OutFile "static/htmx-ext-sse.js"
Invoke-WebRequest "https://unpkg.com/alpinejs@3.14.9/dist/cdn.min.js" -OutFile "static/alpine.min.js"
Invoke-WebRequest "https://cdn.tailwindcss.com" -OutFile "static/tailwind-cdn.js"
```

- [ ] **Step 2: Verify sizes**

```powershell
Get-Item static/htmx.min.js, static/htmx-ext-sse.js, static/alpine.min.js, static/tailwind-cdn.js | Select-Object Name, @{N='KB';E={[math]::Round($_.Length/1KB,1)}}
```

Expected: htmx ~20 KB, sse ~3 KB, alpine ~44 KB, tailwind-cdn ~110–120 KB.

- [ ] **Step 3: Commit**

```powershell
git add static/htmx.min.js static/htmx-ext-sse.js static/alpine.min.js static/tailwind-cdn.js
git commit -m "feat: commit htmx 2.0.4 + alpine 3.14.9 + tailwind cdn as static assets"
```

---

## Task 2: Update render.py + rewrite base.html (Dark Pro sidebar shell)

**Files:**
- Modify: `agentic_redteam/web/render.py`
- Modify: `agentic_redteam/web/app.py`
- Modify: `agentic_redteam/web/templates/base.html`

- [ ] **Step 1: Update render.py to inject `current_path` and `demo_mode` into every template**

Replace the full contents of `agentic_redteam/web/render.py`:

```python
from __future__ import annotations

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES)),
    autoescape=select_autoescape(["html"]),
)
_env.filters["pct"] = lambda v: f"{(v or 0) * 100:.0f}%"


def render(name: str, **ctx) -> str:
    request = ctx.pop("request", None)
    ctx.setdefault("current_path", str(request.url.path) if request else "/")
    ctx.setdefault("demo_mode", os.environ.get("DEMO_MODE") == "1")
    return _env.get_template(name).render(**ctx)
```

- [ ] **Step 2: Run existing tests to verify render.py change is safe**

```powershell
pyritpocvenv\Scripts\python.exe -m pytest tests/ -q
```

Expected: same pass count as before (124 passed + 4 skipped on laptop).

- [ ] **Step 3: Add `request=request` to all render() calls in app.py**

In `agentic_redteam/web/app.py`, also add `request: Request` parameter to `wizard_route` (currently it has no params). Then update all five render calls:

```python
# wizard_route — add request parameter
@app.get("/")
async def wizard_route(request: Request):
    from agentic_redteam.web.presenters import wizard_view
    html = render("wizard.html", title="New Run", wizard=wizard_view(catalog), request=request)
    from starlette.responses import HTMLResponse
    return HTMLResponse(html)

# run_detail
html = render("live.html", title=f"Run {run_id}", run_id=run_id, ctx=ctx, request=request)

# run_report
html = render("report.html", title=f"Report — {run_id}", ctx=ctx, request=request)

# run_list
html = render("runs.html", title="Runs", rows=rows, request=request)
```

(The `/runs/{run_id}` and `/runs/{run_id}/report` routes already have `request: Request` — just add `request=request` to the render call.)

- [ ] **Step 4: Run tests again — must still pass**

```powershell
pyritpocvenv\Scripts\python.exe -m pytest tests/ -q
```

Expected: same pass count.

- [ ] **Step 5: Rewrite base.html**

Replace the full contents of `agentic_redteam/web/templates/base.html`:

```html
<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ title }} — PyRIT Red-Team</title>
  <script src="/static/tailwind-cdn.js"></script>
  <script>
    tailwind.config = {
      theme: { extend: { colors: { 'gray-925': '#0f1117', 'gray-850': '#1a1f2e' } } }
    }
  </script>
  <style>[x-cloak]{display:none!important}</style>
</head>
<body class="h-full bg-gray-925 text-gray-100 flex" x-data>

  <!-- Sidebar -->
  <aside class="w-60 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col h-screen sticky top-0 z-10">
    <div class="px-5 py-4 border-b border-gray-800">
      <div class="flex items-center gap-2">
        <span class="text-red-500 text-xl leading-none">⚡</span>
        <span class="text-white font-bold text-base tracking-wide">PyRIT</span>
      </div>
      <div class="text-gray-500 text-xs mt-1">AI Red-Team Platform</div>
    </div>

    <nav class="flex-1 px-3 py-4 space-y-0.5">
      <a href="/"
         class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors
                {% if current_path == '/' %}text-red-400 bg-gray-800 border-l-2 border-red-500 pl-2.5{% else %}text-gray-400 hover:text-gray-100 hover:bg-gray-800{% endif %}">
        <span>⚡</span><span>New Run</span>
      </a>
      <a href="/runs"
         class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors
                {% if current_path.startswith('/runs') %}text-red-400 bg-gray-800 border-l-2 border-red-500 pl-2.5{% else %}text-gray-400 hover:text-gray-100 hover:bg-gray-800{% endif %}">
        <span>📋</span><span>Run History</span>
      </a>
    </nav>

    <div class="px-4 py-3 border-t border-gray-800 space-y-1.5">
      {% if demo_mode %}
      <span class="inline-flex items-center gap-1.5 bg-amber-950 text-amber-400 text-xs font-medium px-2 py-1 rounded border border-amber-800">
        <span class="w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse"></span>DEMO MODE
      </span>
      {% endif %}
      <div class="text-gray-600 text-xs">v0.13.0</div>
    </div>
  </aside>

  <!-- Main content -->
  <main class="flex-1 overflow-y-auto min-h-screen">
    {% block body %}{% endblock %}
  </main>

  <script src="/static/htmx.min.js"></script>
  <script src="/static/htmx-ext-sse.js"></script>
  <script src="/static/alpine.min.js" defer></script>
</body>
</html>
```

- [ ] **Step 6: Smoke-test base layout in DEMO_MODE**

```powershell
$env:DEMO_MODE="1"; pyritpocvenv\Scripts\python.exe scripts/serve.py
```

Open http://localhost:8006 — verify: dark background, ⚡ PyRIT sidebar, nav links, DEMO MODE pulsing amber badge. Pages may look unstyled (templates not yet rewritten) but the shell must render.

- [ ] **Step 7: Commit**

```powershell
git add agentic_redteam/web/render.py agentic_redteam/web/app.py agentic_redteam/web/templates/base.html
git commit -m "feat: Dark Pro sidebar shell — Tailwind + htmx + Alpine loaded from static"
```

---

## Task 3: Wizard — partial routes + step templates + wizard.html

**Files:**
- Modify: `agentic_redteam/web/app.py`
- Modify: `tests/web/test_app.py`
- Modify: `agentic_redteam/web/templates/wizard.html`
- Create: `agentic_redteam/web/templates/partials/` (directory + 6 step files)

- [ ] **Step 1: Write failing tests for the two new wizard routes**

Add to the bottom of `tests/web/test_app.py`:

```python
def test_wizard_step_get_returns_partial(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    from agentic_redteam.web.app import create_app
    app = create_app(store_path=":memory:")

    async def go():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            r = await c.get("/wizard/step/1")
            assert r.status_code == 200
            assert "target_endpoint" in r.text
            assert "<!DOCTYPE" not in r.text  # partial only, no base template

    asyncio.run(go())


def test_wizard_step_next_validates_required_fields(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    from agentic_redteam.web.app import create_app
    app = create_app(store_path=":memory:")

    async def go():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            # Post step 1 with empty fields — must get error, not advance
            r = await c.post("/wizard/step/1/next",
                             data={"target_endpoint": "", "target_model": "", "completed_steps": ""})
            assert r.status_code == 200
            assert "required" in r.text.lower() or "endpoint" in r.text.lower()
            assert "target_endpoint" in r.text  # still on step 1

    asyncio.run(go())


def test_wizard_step_next_advances_on_valid_data(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    from agentic_redteam.web.app import create_app
    app = create_app(store_path=":memory:")

    async def go():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            r = await c.post("/wizard/step/1/next", data={
                "target_endpoint": "http://gateway/v1",
                "target_model": "gpt-4o",
                "target_api_key_env": "",
                "completed_steps": "",
            })
            assert r.status_code == 200
            # Should now show step 2 content (scope/presets)
            assert "preset" in r.text.lower() or "scope" in r.text.lower()
            # Step 1 hidden fields must be carried forward
            assert "http://gateway/v1" in r.text

    asyncio.run(go())
```

- [ ] **Step 2: Run tests to confirm they fail (routes don't exist yet)**

```powershell
pyritpocvenv\Scripts\python.exe -m pytest tests/web/test_app.py -k "wizard" -v
```

Expected: 3 FAILED with 404 Not Found or AttributeError.

- [ ] **Step 3: Add wizard partial routes and helpers to app.py**

Add the following to `agentic_redteam/web/app.py` — insert after the existing `wizard_route` handler (around line 75), before `_build_run_request`:

```python
# ── Step fields per wizard step (used to exclude them from hidden inputs) ──
_STEP_FIELDS: dict[int, set[str]] = {
    1: {"target_endpoint", "target_model", "target_api_key_env"},
    2: {"preset", "plugin_ids", "strategy_ids", "scope_mode"},
    3: {"adversarial_endpoint", "adversarial_model", "adversarial_api_key_env"},
    4: {"judge_endpoint", "judge_model", "judge_api_key_env"},
    5: {"purpose", "tools", "roles", "data_channels", "entities"},
    6: {"n", "concurrency", "requested_by", "policy_text"},
}
_ALWAYS_EXCLUDE = {"completed_steps", "scope_mode"}


def _hidden_fields(data: dict, current_n: int) -> str:
    """Return hidden <input> elements for all accumulated data except current step's fields."""
    from markupsafe import Markup, escape
    exclude = _STEP_FIELDS.get(current_n, set()) | _ALWAYS_EXCLUDE
    parts = []
    for k, v in data.items():
        if k in exclude:
            continue
        values = v if isinstance(v, list) else [v]
        for val in values:
            parts.append(f'<input type="hidden" name="{escape(k)}" value="{escape(str(val))}">')
    return Markup("\n".join(parts))


def _wizard_ctx(n: int, data: dict, errors: dict | None = None) -> dict:
    from agentic_redteam.web.presenters import wizard_view
    return {
        "n": n,
        "data": data,
        "errors": errors or {},
        "wizard": wizard_view(catalog),
        "hidden": _hidden_fields(data, n),
        "completed_steps": data.get("completed_steps", ""),
    }


@app.get("/wizard/step/{n}")
async def wizard_step_get(n: int, request: Request):
    from starlette.responses import HTMLResponse
    params = dict(request.query_params)
    # Multi-value query params (plugin_ids, strategy_ids)
    for key in ("plugin_ids", "strategy_ids"):
        vals = request.query_params.getlist(key)
        if vals:
            params[key] = vals
    ctx = _wizard_ctx(n, params)
    return HTMLResponse(render(f"partials/wizard_step_{n}.html", **ctx))


@app.post("/wizard/step/{n}")
async def wizard_step_post(n: int, request: Request):
    """Re-render step n with form data (Back navigation / completed-step edit)."""
    from starlette.responses import HTMLResponse
    form = await request.form()
    data = dict(form)
    for key in ("plugin_ids", "strategy_ids"):
        vals = form.getlist(key)
        if vals:
            data[key] = vals
    ctx = _wizard_ctx(n, data)
    return HTMLResponse(render(f"partials/wizard_step_{n}.html", **ctx))


@app.post("/wizard/step/{n}/next")
async def wizard_step_next(n: int, request: Request):
    from starlette.responses import HTMLResponse
    form = await request.form()
    data = dict(form)
    for key in ("plugin_ids", "strategy_ids"):
        vals = form.getlist(key)
        if vals:
            data[key] = vals

    errors: dict[str, str] = {}
    if n == 1:
        if not data.get("target_endpoint", "").strip():
            errors["target_endpoint"] = "Endpoint is required"
        if not data.get("target_model", "").strip():
            errors["target_model"] = "Model name is required"
    elif n == 4:
        if not data.get("judge_endpoint", "").strip():
            errors["judge_endpoint"] = "Endpoint is required"
        if not data.get("judge_model", "").strip():
            errors["judge_model"] = "Model name is required"

    if errors:
        ctx = _wizard_ctx(n, data, errors)
        return HTMLResponse(render(f"partials/wizard_step_{n}.html", **ctx))

    # Mark step n complete, advance to n+1
    done = {int(x) for x in data.get("completed_steps", "").split(",") if x.strip().isdigit()}
    done.add(n)
    data["completed_steps"] = ",".join(str(x) for x in sorted(done))

    next_n = min(n + 1, 6)
    ctx = _wizard_ctx(next_n, data)
    return HTMLResponse(render(f"partials/wizard_step_{next_n}.html", **ctx))
```

- [ ] **Step 4: Run the three new tests — must now pass**

```powershell
pyritpocvenv\Scripts\python.exe -m pytest tests/web/test_app.py -k "wizard" -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Create partials directory**

```powershell
New-Item -ItemType Directory -Path "agentic_redteam/web/templates/partials" -Force
```

- [ ] **Step 6: Create wizard_step_1.html (Target LLM)**

Write `agentic_redteam/web/templates/partials/wizard_step_1.html`:

```html
<div data-step="1" class="space-y-5">
  <div>
    <h2 class="text-lg font-semibold text-white">Target LLM</h2>
    <p class="text-sm text-gray-400 mt-1">The AI system you want to red-team.</p>
  </div>

  {{ hidden }}
  <input type="hidden" name="completed_steps" value="{{ completed_steps }}">

  <div class="space-y-4">
    <div>
      <label class="block text-sm font-medium text-gray-300 mb-1.5">
        Endpoint URL <span class="text-red-400">*</span>
      </label>
      <input type="text" name="target_endpoint"
             value="{{ data.get('target_endpoint', '') }}"
             placeholder="https://gateway/v1"
             class="w-full bg-gray-800 border {{ 'border-red-500' if errors.get('target_endpoint') else 'border-gray-700' }} rounded-lg px-3 py-2.5 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-colors">
      {% if errors.get('target_endpoint') %}
      <p class="mt-1 text-xs text-red-400">{{ errors['target_endpoint'] }}</p>
      {% endif %}
    </div>

    <div>
      <label class="block text-sm font-medium text-gray-300 mb-1.5">
        Model Name <span class="text-red-400">*</span>
      </label>
      <input type="text" name="target_model"
             value="{{ data.get('target_model', '') }}"
             placeholder="e.g. gpt-4o, claude-3-5-sonnet"
             class="w-full bg-gray-800 border {{ 'border-red-500' if errors.get('target_model') else 'border-gray-700' }} rounded-lg px-3 py-2.5 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-colors">
      {% if errors.get('target_model') %}
      <p class="mt-1 text-xs text-red-400">{{ errors['target_model'] }}</p>
      {% endif %}
    </div>

    <div>
      <label class="block text-sm font-medium text-gray-300 mb-1.5">
        API Key Env Var <span class="text-gray-500 font-normal">(optional)</span>
      </label>
      <input type="text" name="target_api_key_env"
             value="{{ data.get('target_api_key_env', '') }}"
             placeholder="OPENAI_CHAT_KEY"
             class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-colors">
    </div>
  </div>

  <div class="flex justify-end pt-4 border-t border-gray-800">
    <button type="button"
            hx-post="/wizard/step/1/next"
            hx-include="closest form"
            hx-target="#step-content"
            hx-swap="innerHTML"
            class="bg-red-600 hover:bg-red-700 active:bg-red-800 text-white font-medium px-5 py-2.5 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
      Next <span aria-hidden>→</span>
    </button>
  </div>
</div>
```

- [ ] **Step 7: Create wizard_step_2.html (Scope)**

Write `agentic_redteam/web/templates/partials/wizard_step_2.html`:

```html
<div data-step="2" class="space-y-5" x-data="{ mode: '{{ 'custom' if data.get('plugin_ids') else 'preset' }}' }">
  <div>
    <h2 class="text-lg font-semibold text-white">Scope</h2>
    <p class="text-sm text-gray-400 mt-1">Choose a framework preset or hand-pick plugins and strategies.</p>
  </div>

  {{ hidden }}
  <input type="hidden" name="completed_steps" value="{{ completed_steps }}">

  <!-- Mode toggle -->
  <div class="flex gap-1 bg-gray-800 p-1 rounded-lg w-fit">
    <button type="button" @click="mode='preset'"
            :class="mode==='preset' ? 'bg-gray-700 text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'"
            class="px-4 py-1.5 rounded-md text-sm font-medium transition-all">Use Preset</button>
    <button type="button" @click="mode='custom'"
            :class="mode==='custom' ? 'bg-gray-700 text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'"
            class="px-4 py-1.5 rounded-md text-sm font-medium transition-all">Custom</button>
  </div>

  <!-- Preset panel -->
  <div x-show="mode==='preset'" x-cloak>
    <div class="grid grid-cols-2 gap-3">
      {% for p in wizard.presets %}
      {% if p.plugin_count > 0 %}
      <label class="group cursor-pointer">
        <input type="radio" name="preset" value="{{ p.id }}" class="sr-only peer"
               {% if data.get('preset') == p.id or (loop.first and not data.get('preset')) %}checked{% endif %}>
        <div class="border-2 rounded-xl p-4 transition-all h-full
                    peer-checked:border-red-500 peer-checked:bg-red-950/20
                    border-gray-700 hover:border-gray-600 bg-gray-800/50">
          <div class="font-semibold text-sm text-white">{{ p.title }}</div>
          <div class="text-xs text-gray-400 mt-1">{{ p.framework }} · {{ p.plugin_count }} plugin{{ 's' if p.plugin_count != 1 }}</div>
        </div>
      </label>
      {% endif %}
      {% endfor %}
    </div>
  </div>

  <!-- Custom panel -->
  <div x-show="mode==='custom'" x-cloak class="space-y-3">
    <!-- Plugins -->
    <details open class="bg-gray-850 rounded-xl border border-gray-700">
      <summary class="px-4 py-3 font-medium text-sm text-gray-200 cursor-pointer select-none hover:text-white list-none flex justify-between items-center">
        <span>Plugins <span class="text-gray-500 font-normal">({{ wizard.groups.values() | map('length') | sum }} total)</span></span>
        <span class="text-gray-500 text-xs">▼</span>
      </summary>
      <div class="px-4 pb-4 divide-y divide-gray-800">
        {% for group, plugins in wizard.groups.items() %}
        <div class="pt-3 first:pt-0">
          <div class="text-xs text-gray-500 uppercase tracking-wider mb-2">{{ group }}</div>
          <div class="space-y-0.5">
            {% for pl in plugins %}
            <label class="flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-gray-800 cursor-pointer {{ 'opacity-40 cursor-not-allowed' if not pl.runnable }}">
              <input type="checkbox" name="plugin_ids" value="{{ pl.id }}"
                     {{ 'disabled' if not pl.runnable }}
                     {{ 'checked' if pl.id in (data.get('plugin_ids') or []) }}
                     class="rounded border-gray-600 bg-gray-700 text-red-500 focus:ring-red-500 focus:ring-offset-gray-900">
              <span class="text-sm text-gray-300 flex-1">{{ pl.name }}</span>
              <span class="text-xs px-1.5 py-0.5 rounded font-medium
                {{ 'bg-red-900/50 text-red-400' if pl.severity == 'critical'
                   else 'bg-amber-900/50 text-amber-400' if pl.severity == 'high'
                   else 'bg-blue-900/50 text-blue-400' if pl.severity == 'medium'
                   else 'bg-gray-700 text-gray-400' }}">{{ pl.severity }}</span>
              {% if not pl.runnable %}
              <span class="text-xs bg-gray-700 text-gray-500 px-1.5 py-0.5 rounded">needs data</span>
              {% endif %}
            </label>
            {% endfor %}
          </div>
        </div>
        {% endfor %}
      </div>
    </details>

    <!-- Strategies -->
    <details open class="bg-gray-850 rounded-xl border border-gray-700">
      <summary class="px-4 py-3 font-medium text-sm text-gray-200 cursor-pointer select-none hover:text-white list-none flex justify-between items-center">
        <span>Strategies</span>
        <span class="text-gray-500 text-xs">▼</span>
      </summary>
      <div class="px-4 pb-4 grid grid-cols-2 gap-1 mt-2">
        {% for s in wizard.strategies %}
        <label class="flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-gray-800 cursor-pointer {{ 'opacity-40 cursor-not-allowed' if s.disabled }}">
          <input type="checkbox" name="strategy_ids" value="{{ s.id }}"
                 {{ 'checked' if s.id == 'basic' or s.id in (data.get('strategy_ids') or []) }}
                 {{ 'disabled' if s.disabled }}
                 class="rounded border-gray-600 bg-gray-700 text-red-500 focus:ring-red-500 focus:ring-offset-gray-900">
          <span class="text-sm text-gray-300">{{ s.display_name }}</span>
          <span class="font-bold text-sm {{ 'text-green-400' if s.badge == '✓' else 'text-amber-400' if s.badge == '⚠' else 'text-gray-500' }}">{{ s.badge }}</span>
        </label>
        {% endfor %}
      </div>
    </details>
  </div>

  <div class="flex justify-between pt-4 border-t border-gray-800">
    <button type="button"
            hx-post="/wizard/step/1"
            hx-include="closest form"
            hx-target="#step-content"
            hx-swap="innerHTML"
            class="border border-gray-700 hover:border-gray-600 text-gray-400 hover:text-white font-medium px-4 py-2.5 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
      ← Back
    </button>
    <button type="button"
            hx-post="/wizard/step/2/next"
            hx-include="closest form"
            hx-target="#step-content"
            hx-swap="innerHTML"
            class="bg-red-600 hover:bg-red-700 text-white font-medium px-5 py-2.5 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
      Next →
    </button>
  </div>
</div>
```

- [ ] **Step 8: Create wizard_step_3.html (Attacker LLM)**

Write `agentic_redteam/web/templates/partials/wizard_step_3.html`:

```html
<div data-step="3" class="space-y-5">
  <div>
    <h2 class="text-lg font-semibold text-white">Attacker LLM <span class="text-gray-500 font-normal text-base">(optional)</span></h2>
    <p class="text-sm text-gray-400 mt-1">Required for multi-turn strategies (Crescendo, TAP). Leave blank to use basic attacks only.</p>
  </div>

  {{ hidden }}
  <input type="hidden" name="completed_steps" value="{{ completed_steps }}">

  <div class="space-y-4">
    <div>
      <label class="block text-sm font-medium text-gray-300 mb-1.5">Endpoint URL</label>
      <input type="text" name="adversarial_endpoint"
             value="{{ data.get('adversarial_endpoint', '') }}"
             placeholder="http://host.docker.internal:8001/v1"
             class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-colors">
    </div>
    <div>
      <label class="block text-sm font-medium text-gray-300 mb-1.5">Model Name</label>
      <input type="text" name="adversarial_model"
             value="{{ data.get('adversarial_model', '') }}"
             placeholder="Qwen3-35B-A3B-4bit"
             class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-colors">
    </div>
    <div>
      <label class="block text-sm font-medium text-gray-300 mb-1.5">API Key Env Var <span class="text-gray-500 font-normal">(optional)</span></label>
      <input type="text" name="adversarial_api_key_env"
             value="{{ data.get('adversarial_api_key_env', '') }}"
             placeholder="(leave blank if not required)"
             class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-colors">
    </div>
  </div>

  <div class="flex justify-between pt-4 border-t border-gray-800">
    <button type="button"
            hx-post="/wizard/step/2"
            hx-include="closest form"
            hx-target="#step-content"
            hx-swap="innerHTML"
            class="border border-gray-700 hover:border-gray-600 text-gray-400 hover:text-white font-medium px-4 py-2.5 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
      ← Back
    </button>
    <button type="button"
            hx-post="/wizard/step/3/next"
            hx-include="closest form"
            hx-target="#step-content"
            hx-swap="innerHTML"
            class="bg-red-600 hover:bg-red-700 text-white font-medium px-5 py-2.5 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
      Next →
    </button>
  </div>
</div>
```

- [ ] **Step 9: Create wizard_step_4.html (Judge LLM)**

Write `agentic_redteam/web/templates/partials/wizard_step_4.html`:

```html
<div data-step="4" class="space-y-5">
  <div>
    <h2 class="text-lg font-semibold text-white">Judge LLM</h2>
    <p class="text-sm text-gray-400 mt-1">Scores each attack attempt. Use your internal gateway.</p>
  </div>

  {{ hidden }}
  <input type="hidden" name="completed_steps" value="{{ completed_steps }}">

  <div class="space-y-4">
    <div>
      <label class="block text-sm font-medium text-gray-300 mb-1.5">Endpoint URL <span class="text-red-400">*</span></label>
      <input type="text" name="judge_endpoint"
             value="{{ data.get('judge_endpoint', '') }}"
             placeholder="https://gateway/v1"
             class="w-full bg-gray-800 border {{ 'border-red-500' if errors.get('judge_endpoint') else 'border-gray-700' }} rounded-lg px-3 py-2.5 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-colors">
      {% if errors.get('judge_endpoint') %}<p class="mt-1 text-xs text-red-400">{{ errors['judge_endpoint'] }}</p>{% endif %}
    </div>
    <div>
      <label class="block text-sm font-medium text-gray-300 mb-1.5">Model Name <span class="text-red-400">*</span></label>
      <input type="text" name="judge_model"
             value="{{ data.get('judge_model', '') }}"
             placeholder="e.g. gpt-4o"
             class="w-full bg-gray-800 border {{ 'border-red-500' if errors.get('judge_model') else 'border-gray-700' }} rounded-lg px-3 py-2.5 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-colors">
      {% if errors.get('judge_model') %}<p class="mt-1 text-xs text-red-400">{{ errors['judge_model'] }}</p>{% endif %}
    </div>
    <div>
      <label class="block text-sm font-medium text-gray-300 mb-1.5">API Key Env Var <span class="text-gray-500 font-normal">(optional)</span></label>
      <input type="text" name="judge_api_key_env"
             value="{{ data.get('judge_api_key_env', '') }}"
             placeholder="OPENAI_CHAT_KEY"
             class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-colors">
    </div>
  </div>

  <div class="flex justify-between pt-4 border-t border-gray-800">
    <button type="button"
            hx-post="/wizard/step/3"
            hx-include="closest form"
            hx-target="#step-content"
            hx-swap="innerHTML"
            class="border border-gray-700 hover:border-gray-600 text-gray-400 hover:text-white font-medium px-4 py-2.5 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
      ← Back
    </button>
    <button type="button"
            hx-post="/wizard/step/4/next"
            hx-include="closest form"
            hx-target="#step-content"
            hx-swap="innerHTML"
            class="bg-red-600 hover:bg-red-700 text-white font-medium px-5 py-2.5 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
      Next →
    </button>
  </div>
</div>
```

- [ ] **Step 10: Create wizard_step_5.html (App Profile)**

Write `agentic_redteam/web/templates/partials/wizard_step_5.html`:

```html
<div data-step="5" class="space-y-5">
  <div>
    <h2 class="text-lg font-semibold text-white">App Profile</h2>
    <p class="text-sm text-gray-400 mt-1">Describe the target application to ground the attack objectives.</p>
  </div>

  {{ hidden }}
  <input type="hidden" name="completed_steps" value="{{ completed_steps }}">

  <div class="space-y-4">
    <div>
      <label class="block text-sm font-medium text-gray-300 mb-1.5">Purpose</label>
      <input type="text" name="purpose"
             value="{{ data.get('purpose', '') }}"
             placeholder="e.g. internal banking assistant for account enquiries"
             class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-colors">
    </div>
    <div>
      <label class="block text-sm font-medium text-gray-300 mb-1.5">Tools <span class="text-gray-500 font-normal">(comma-separated)</span></label>
      <input type="text" name="tools"
             value="{{ data.get('tools', '') }}"
             placeholder="account_lookup, fund_transfer, statement_download"
             class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-colors">
    </div>
    <div>
      <label class="block text-sm font-medium text-gray-300 mb-1.5">Roles <span class="text-gray-500 font-normal">(comma-separated)</span></label>
      <input type="text" name="roles"
             value="{{ data.get('roles', '') }}"
             placeholder="customer, admin, support_agent"
             class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-colors">
    </div>
    <div>
      <label class="block text-sm font-medium text-gray-300 mb-1.5">Data Channels <span class="text-gray-500 font-normal">(comma-separated)</span></label>
      <input type="text" name="data_channels"
             value="{{ data.get('data_channels', '') }}"
             placeholder="chat, email, voice"
             class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-colors">
    </div>
    <div>
      <label class="block text-sm font-medium text-gray-300 mb-1.5">Entities <span class="text-gray-500 font-normal">(comma-separated)</span></label>
      <input type="text" name="entities"
             value="{{ data.get('entities', '') }}"
             placeholder="customer_id, account_number, sort_code"
             class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-colors">
    </div>
  </div>

  <div class="flex justify-between pt-4 border-t border-gray-800">
    <button type="button"
            hx-post="/wizard/step/4"
            hx-include="closest form"
            hx-target="#step-content"
            hx-swap="innerHTML"
            class="border border-gray-700 hover:border-gray-600 text-gray-400 hover:text-white font-medium px-4 py-2.5 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
      ← Back
    </button>
    <button type="button"
            hx-post="/wizard/step/5/next"
            hx-include="closest form"
            hx-target="#step-content"
            hx-swap="innerHTML"
            class="bg-red-600 hover:bg-red-700 text-white font-medium px-5 py-2.5 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
      Next →
    </button>
  </div>
</div>
```

- [ ] **Step 11: Create wizard_step_6.html (Review & Launch)**

Write `agentic_redteam/web/templates/partials/wizard_step_6.html`:

```html
<div data-step="6" class="space-y-5">
  <div>
    <h2 class="text-lg font-semibold text-white">Review & Launch</h2>
    <p class="text-sm text-gray-400 mt-1">Confirm your configuration, adjust run settings, then launch.</p>
  </div>

  {{ hidden }}
  <input type="hidden" name="completed_steps" value="{{ completed_steps }}">

  <!-- Summary -->
  <div class="bg-gray-800/50 border border-gray-700 rounded-xl p-4 space-y-2 text-sm">
    <div class="flex justify-between"><span class="text-gray-400">Target</span><span class="text-gray-100 font-mono text-xs">{{ data.get('target_endpoint', '—') }} / {{ data.get('target_model', '—') }}</span></div>
    <div class="flex justify-between"><span class="text-gray-400">Scope</span><span class="text-gray-100">{{ ('Preset: ' + data.get('preset', '')) if data.get('preset') else (data.get('plugin_ids', [])|length|string + ' custom plugin(s)') }}</span></div>
    <div class="flex justify-between"><span class="text-gray-400">Judge</span><span class="text-gray-100 font-mono text-xs">{{ data.get('judge_endpoint', '—') }} / {{ data.get('judge_model', '—') }}</span></div>
    {% if data.get('purpose') %}
    <div class="flex justify-between"><span class="text-gray-400">Purpose</span><span class="text-gray-100">{{ data.get('purpose') }}</span></div>
    {% endif %}
  </div>

  <!-- Run settings -->
  <div class="bg-gray-850 border border-gray-700 rounded-xl p-4 space-y-4">
    <h3 class="text-sm font-semibold text-gray-200">Run Settings</h3>
    <div class="grid grid-cols-2 gap-4">
      <div>
        <label class="block text-xs font-medium text-gray-400 mb-1.5">Objectives per plugin</label>
        <input type="number" name="n" value="{{ data.get('n', '5') }}" min="1" max="20"
               class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500">
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-400 mb-1.5">Concurrency</label>
        <input type="number" name="concurrency" value="{{ data.get('concurrency', '4') }}" min="1" max="16"
               class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500">
      </div>
    </div>
    <div>
      <label class="block text-xs font-medium text-gray-400 mb-1.5">Requested by <span class="text-gray-600">(audit trail)</span></label>
      <input type="text" name="requested_by" value="{{ data.get('requested_by', '') }}"
             placeholder="your name or team"
             class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500">
    </div>
    <div>
      <label class="block text-xs font-medium text-gray-400 mb-1.5">Policy text <span class="text-gray-600">(optional — for policy-enforcement plugins)</span></label>
      <textarea name="policy_text" rows="3"
                placeholder="Paste a policy statement to test compliance against…"
                class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 resize-none">{{ data.get('policy_text', '') }}</textarea>
    </div>
  </div>

  <div class="flex justify-between pt-4 border-t border-gray-800">
    <button type="button"
            hx-post="/wizard/step/5"
            hx-include="closest form"
            hx-target="#step-content"
            hx-swap="innerHTML"
            class="border border-gray-700 hover:border-gray-600 text-gray-400 hover:text-white font-medium px-4 py-2.5 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
      ← Back
    </button>
    <button type="submit"
            form="wizard-form"
            class="bg-red-600 hover:bg-red-700 active:bg-red-800 text-white font-semibold px-6 py-2.5 rounded-lg text-sm transition-colors inline-flex items-center gap-2 shadow-lg shadow-red-900/30">
      ⚡ Launch Run
    </button>
  </div>
</div>
```

- [ ] **Step 12: Rewrite wizard.html**

Replace the full contents of `agentic_redteam/web/templates/wizard.html`:

```html
{% extends "base.html" %}
{% block body %}
<div class="p-6 max-w-5xl mx-auto">
  <div class="mb-6">
    <h1 class="text-2xl font-bold text-white">New Red-Team Run</h1>
    <p class="text-gray-400 text-sm mt-1">Configure target, scope, and attack parameters step by step.</p>
  </div>

  <form id="wizard-form" method="post" action="/runs"
        x-data="{
          currentStep: 1,
          updateStep() {
            const el = document.querySelector('#step-content [data-step]');
            if (el) this.currentStep = parseInt(el.dataset.step);
          }
        }"
        @htmx:after-swap.window="updateStep()">

    <div class="flex gap-6">
      <!-- Step list -->
      <div class="w-44 flex-shrink-0 pt-1">
        <div class="space-y-0.5">
          {% for step_n, step_label in [(1,'Target LLM'),(2,'Scope'),(3,'Attacker LLM'),(4,'Judge LLM'),(5,'App Profile'),(6,'Review')] %}
          <div class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm cursor-default transition-colors"
               :class="{
                 'text-red-400 bg-gray-800 border-l-2 border-red-500 pl-2.5': currentStep === {{ step_n }},
                 'text-green-400 hover:bg-gray-800 cursor-pointer': currentStep > {{ step_n }},
                 'text-gray-600': currentStep < {{ step_n }}
               }"
               @click="if (currentStep > {{ step_n }}) htmx.ajax('POST', '/wizard/step/{{ step_n }}', {target: '#step-content', swap: 'innerHTML', values: Object.fromEntries(new FormData(document.getElementById('wizard-form')))})">
            <div class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 transition-all"
                 :class="{
                   'bg-red-500 text-white': currentStep === {{ step_n }},
                   'bg-green-500 text-gray-900': currentStep > {{ step_n }},
                   'bg-gray-800 text-gray-600 border border-gray-700': currentStep < {{ step_n }}
                 }">
              <template x-if="currentStep <= {{ step_n }}"><span>{{ step_n }}</span></template>
              <template x-if="currentStep > {{ step_n }}"><span>✓</span></template>
            </div>
            <span class="leading-tight">{{ step_label }}</span>
          </div>
          {% endfor %}
        </div>
      </div>

      <!-- Step content (htmx swap target) -->
      <div id="step-content" class="flex-1 bg-gray-850 rounded-2xl border border-gray-800 p-6 min-h-[400px]">
        {% include "partials/wizard_step_1.html" %}
      </div>
    </div>

  </form>
</div>
{% endblock %}
```

- [ ] **Step 13: Smoke-test the wizard in DEMO_MODE**

```powershell
$env:DEMO_MODE="1"; pyritpocvenv\Scripts\python.exe scripts/serve.py
```

Open http://localhost:8006. Verify:
- Sidebar present, "New Run" active link
- Two-column layout: step list left, step 1 form right
- Fill in Target LLM fields, click Next → step 2 (Scope) loads via htmx, step 1 circle turns green ✓
- Select a preset, click Next → step 3 loads
- Continue to step 6, verify Review summary shows Target/Scope/Judge entries
- Click "← Back" → returns to previous step with values pre-filled

- [ ] **Step 14: Run all tests**

```powershell
pyritpocvenv\Scripts\python.exe -m pytest tests/ -q
```

Expected: all previous tests still pass + 3 new wizard tests pass.

- [ ] **Step 15: Commit**

```powershell
git add agentic_redteam/web/app.py tests/web/test_app.py agentic_redteam/web/templates/
git commit -m "feat: htmx wizard with step-list nav, 6 Tailwind step partials, Dark Pro theme"
```

---

## Task 4: Update SSE + live run page

**Files:**
- Modify: `agentic_redteam/web/app.py` (SSE generator)
- Create: `agentic_redteam/web/templates/partials/feed_row.html`
- Create: `agentic_redteam/web/templates/partials/run_finished.html`
- Modify: `agentic_redteam/web/templates/live.html`

- [ ] **Step 1: Create feed_row.html partial**

Write `agentic_redteam/web/templates/partials/feed_row.html`:

```html
<div class="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-gray-800/50 transition-colors text-sm border-b border-gray-800/50 last:border-0"
     data-run-event="execution_done" data-status="{{ status }}">
  <span class="flex-shrink-0 text-base leading-none">
    {%- if status == 'succeeded' -%}⚠️{%- elif status == 'error' -%}🔴{%- else -%}✅{%- endif -%}
  </span>
  <span class="flex-1 text-gray-200 font-mono text-xs truncate">{{ plugin_id }}</span>
  <span class="text-gray-500 text-xs">{{ strategy_id }}</span>
  <span class="text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0
    {{ 'bg-red-900/60 text-red-300' if status == 'succeeded'
       else 'bg-green-900/60 text-green-300' if status == 'defended'
       else 'bg-amber-900/60 text-amber-300' }}">
    {{ status }}
  </span>
</div>
```

- [ ] **Step 2: Create run_finished.html partial**

Write `agentic_redteam/web/templates/partials/run_finished.html`:

```html
<div id="run-status-sse" class="mt-4 p-4 bg-gray-800/60 border border-gray-700 rounded-xl flex items-center justify-between">
  <div class="flex items-center gap-3">
    <span class="text-green-400 text-xl">✓</span>
    <div>
      <div class="text-white font-semibold text-sm">Run {{ status }}</div>
      <div class="text-gray-400 text-xs mt-0.5">All executions complete</div>
    </div>
  </div>
  <a href="/runs/{{ run_id }}/report"
     class="bg-red-600 hover:bg-red-700 text-white font-medium px-4 py-2 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
    View Full Report →
  </a>
</div>
```

- [ ] **Step 3: Update the SSE generator in app.py to emit named events with HTML fragments**

In `agentic_redteam/web/app.py`, replace the `_sse` helper and update the `run_events` generator.

Replace the existing `_sse` function:

```python
def _sse(event: str, html: str) -> str:
    # SSE format: event name + single-line data (strip internal newlines)
    payload = html.replace("\n", " ").replace("\r", "")
    return f"event: {event}\ndata: {payload}\n\n"
```

Update the `generate()` function inside `run_events` — replace the two `yield _sse(d)` calls:

```python
# Replay already-completed executions from the store
for rec in store.get_executions(run_id):
    html = render("partials/feed_row.html",
                  plugin_id=rec.plugin_id,
                  strategy_id=rec.strategy_id,
                  status=rec.status)
    yield _sse("execution_done", html)

# Check if run is already final
row = store.get_run(run_id)
if row and row.get("status") in _FINAL:
    html = render("partials/run_finished.html",
                  run_id=run_id, status=row["status"])
    yield _sse("run_finished", html)
    return

# Stream live events
while True:
    if await request.is_disconnected():
        break
    try:
        event = await asyncio.wait_for(q.get(), timeout=1.0)
    except asyncio.TimeoutError:
        continue

    if event.run_id != run_id:
        continue

    if event.kind == "execution_done":
        html = render("partials/feed_row.html",
                      plugin_id=event.plugin_id,
                      strategy_id=event.strategy_id,
                      status=event.status)
        yield _sse("execution_done", html)
    elif event.kind == "run_finished":
        row = store.get_run(run_id)
        final_status = row["status"] if row else "completed"
        html = render("partials/run_finished.html",
                      run_id=run_id, status=final_status)
        yield _sse("run_finished", html)
        break
    else:
        d = event.model_dump()
        yield _sse(event.kind, json.dumps(d))
```

Note: `event.plugin_id`, `event.strategy_id`, `event.status` — verify these fields exist on the progress bus event model. If the event model uses different field names, check `agentic_redteam/progress.py` and adjust.

- [ ] **Step 4: Rewrite live.html**

Replace the full contents of `agentic_redteam/web/templates/live.html`:

```html
{% extends "base.html" %}
{% block body %}
<div class="p-6 max-w-5xl mx-auto">

  <!-- Header -->
  <div class="flex items-start justify-between mb-6">
    <div>
      <div class="flex items-center gap-3">
        <h1 class="text-2xl font-bold text-white font-mono">{{ run_id }}</h1>
        <span class="text-xs px-2.5 py-1 rounded-full font-medium border
          {% if ctx.summary.status == 'running' %}bg-amber-950 text-amber-300 border-amber-800 animate-pulse
          {% elif ctx.summary.status == 'completed' %}bg-green-950 text-green-300 border-green-800
          {% elif ctx.summary.status == 'failed' %}bg-red-950 text-red-300 border-red-800
          {% else %}bg-gray-800 text-gray-400 border-gray-700{% endif %}">
          {{ ctx.summary.status }}
        </span>
      </div>
      <p class="text-gray-500 text-sm mt-1">Live execution feed</p>
    </div>
    {% if ctx.summary.status not in ('completed', 'stopped', 'failed') %}
    <form method="post" action="/runs/{{ run_id }}/stop">
      <button type="submit"
              class="border border-red-800 text-red-400 hover:bg-red-950 font-medium px-4 py-2 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
        ■ Stop Run
      </button>
    </form>
    {% endif %}
  </div>

  <!-- Progress bar -->
  {% set pct = ((ctx.summary.completed / ctx.summary.total * 100) | int) if ctx.summary.total else 0 %}
  <div class="mb-4">
    <div class="flex justify-between text-xs text-gray-500 mb-1.5">
      <span>{{ ctx.summary.completed }} / {{ ctx.summary.total }} executions</span>
      <span>{{ pct }}%</span>
    </div>
    <div class="h-2 bg-gray-800 rounded-full overflow-hidden">
      <div class="h-full rounded-full transition-all duration-300"
           style="width: {{ pct }}%; background: linear-gradient(90deg, #ef4444, #f97316);"
           id="progress-bar-fill"></div>
    </div>
  </div>

  <!-- Stats cards -->
  <div class="grid grid-cols-4 gap-3 mb-6"
       x-data="{
         done: {{ ctx.summary.completed }},
         total: {{ ctx.summary.total or 0 }},
         succeeded: {{ ctx.summary.succeeded or 0 }},
         defended: 0,
         errors: {{ ctx.summary.errors or 0 }}
       }"
       id="stats-bar"
       @htmx:after-swap.window="
         const row = $event.detail.target.querySelector('[data-run-event=execution_done]')
                  || $event.detail.target.closest('[data-run-event=execution_done]');
         if (row) {
           done++;
           const s = row.dataset.status;
           if (s==='succeeded') succeeded++;
           else if (s==='defended') defended++;
           else if (s==='error') errors++;
           const bar = document.getElementById('progress-bar-fill');
           if (bar && total > 0) bar.style.width = Math.round(done/total*100) + '%';
         }
       ">
    <div class="bg-gray-850 border border-gray-800 rounded-xl p-4 text-center">
      <div class="text-2xl font-bold text-white" x-text="done">{{ ctx.summary.completed }}</div>
      <div class="text-xs text-gray-500 mt-1">Done</div>
    </div>
    <div class="bg-gray-850 border border-red-900/30 rounded-xl p-4 text-center">
      <div class="text-2xl font-bold text-red-400" x-text="succeeded">{{ ctx.summary.succeeded or 0 }}</div>
      <div class="text-xs text-gray-500 mt-1">Succeeded</div>
    </div>
    <div class="bg-gray-850 border border-green-900/30 rounded-xl p-4 text-center">
      <div class="text-2xl font-bold text-green-400" x-text="defended">0</div>
      <div class="text-xs text-gray-500 mt-1">Defended</div>
    </div>
    <div class="bg-gray-850 border border-amber-900/30 rounded-xl p-4 text-center">
      <div class="text-2xl font-bold text-amber-400" x-text="errors">{{ ctx.summary.errors or 0 }}</div>
      <div class="text-xs text-gray-500 mt-1">Errors</div>
    </div>
  </div>

  <!-- Completed run banner (shown once run is done) -->
  {% if ctx.summary.status in ('completed', 'stopped') %}
  <div class="mb-4 p-4 bg-gray-800/60 border border-gray-700 rounded-xl flex items-center justify-between">
    <div class="flex items-center gap-3">
      <span class="text-green-400 text-xl">✓</span>
      <div>
        <div class="text-white font-semibold text-sm">Run {{ ctx.summary.status }} — ASR: {{ ctx.overall_asr | pct }}</div>
        <div class="text-gray-400 text-xs mt-0.5">All executions complete</div>
      </div>
    </div>
    <a href="/runs/{{ run_id }}/report"
       class="bg-red-600 hover:bg-red-700 text-white font-medium px-4 py-2 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
      View Full Report →
    </a>
  </div>
  {% endif %}

  <!-- SSE-driven live elements -->
  <div hx-ext="sse" sse-connect="/runs/{{ run_id }}/events">
    <!-- run_finished banner: swapped in by SSE -->
    <div id="run-status-sse" sse-swap="run_finished" hx-swap="outerHTML"></div>

    <!-- Feed: execution_done events prepend rows here -->
    <div class="bg-gray-850 border border-gray-800 rounded-xl overflow-hidden">
      <div class="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
        <span class="text-sm font-medium text-gray-300">Live Feed</span>
        <span class="text-xs text-gray-600">newest first</span>
      </div>
      <div id="feed" sse-swap="execution_done" hx-swap="afterbegin" class="divide-y divide-gray-800/50 max-h-96 overflow-y-auto">
        {% for r in ctx.findings %}
        <div class="flex items-center gap-3 py-2 px-3 rounded-lg text-sm border-b border-gray-800/50">
          <span class="flex-shrink-0">✅</span>
          <span class="flex-1 text-gray-200 font-mono text-xs truncate">{{ r.plugin_id }}</span>
          <span class="text-gray-500 text-xs">{{ r.strategy_id }}</span>
          <span class="text-xs px-2 py-0.5 rounded-full font-medium bg-red-900/60 text-red-300">succeeded</span>
        </div>
        {% endfor %}
      </div>
    </div>
  </div>

</div>
{% endblock %}
```

- [ ] **Step 5: Check progress.py for event field names**

Read `agentic_redteam/progress.py` and verify the event model fields used in the SSE generator (`event.plugin_id`, `event.strategy_id`, `event.status`, `event.kind`, `event.run_id`). Adjust field names in the generator if they differ.

- [ ] **Step 6: Run tests**

```powershell
pyritpocvenv\Scripts\python.exe -m pytest tests/ -q
```

Expected: all tests still pass.

- [ ] **Step 7: Smoke-test live view in DEMO_MODE**

Start server, open http://localhost:8006, launch a run. Watch:
- Stats cards increment as executions stream in
- Feed rows appear (newest first)
- Progress bar advances
- On completion: "View Full Report →" banner appears

- [ ] **Step 8: Commit**

```powershell
git add agentic_redteam/web/app.py agentic_redteam/web/templates/
git commit -m "feat: live run page — htmx-sse feed, stats cards, Dark Pro theme"
```

---

## Task 5: Rewrite report.html

**Files:**
- Modify: `agentic_redteam/web/templates/report.html`

- [ ] **Step 1: Rewrite report.html**

Replace the full contents of `agentic_redteam/web/templates/report.html`:

```html
{% extends "base.html" %}
{% block body %}
<div class="p-6 max-w-5xl mx-auto">

  <!-- Header -->
  <div class="flex items-start justify-between mb-6">
    <div>
      <h1 class="text-2xl font-bold text-white font-mono">{{ ctx.summary.run_id }}</h1>
      <div class="flex items-center gap-3 mt-2">
        <span class="text-xs px-2.5 py-1 rounded-full font-medium border
          {% if ctx.summary.status == 'completed' %}bg-green-950 text-green-300 border-green-800
          {% elif ctx.summary.status == 'failed' %}bg-red-950 text-red-300 border-red-800
          {% else %}bg-gray-800 text-gray-400 border-gray-700{% endif %}">
          {{ ctx.summary.status }}
        </span>
        <span class="text-gray-500 text-sm">{{ ctx.summary.total }} executions</span>
        <span class="font-bold text-sm px-2.5 py-0.5 rounded-lg
          {% set asr = ctx.overall_asr %}
          {% if asr > 0.5 %}bg-red-900/50 text-red-300
          {% elif asr > 0.2 %}bg-amber-900/50 text-amber-300
          {% else %}bg-green-900/50 text-green-300{% endif %}">
          ASR {{ ctx.overall_asr | pct }}
        </span>
      </div>
    </div>
    <div class="flex gap-2 no-print">
      <a href="/runs/{{ ctx.summary.run_id }}/report.json"
         class="border border-gray-700 hover:border-gray-600 text-gray-400 hover:text-white px-3 py-2 rounded-lg text-sm transition-colors inline-flex items-center gap-1.5">
        ⬇ JSON
      </a>
      <button onclick="window.print()"
              class="border border-gray-700 hover:border-gray-600 text-gray-400 hover:text-white px-3 py-2 rounded-lg text-sm transition-colors inline-flex items-center gap-1.5">
        🖨 Print
      </button>
    </div>
  </div>

  <!-- Framework Scorecard -->
  {% set has_scorecard = ctx.framework_scorecard.values() | selectattr('__bool__') | list %}
  {% if has_scorecard %}
  <div class="mb-6">
    <h2 class="text-base font-semibold text-gray-200 mb-3">Framework Scorecard</h2>
    <div class="space-y-2">
      {% for family, codes in ctx.framework_scorecard.items() %}
      {% if codes %}
      <details class="bg-gray-850 border border-gray-800 rounded-xl overflow-hidden group">
        <summary class="px-4 py-3 cursor-pointer select-none hover:bg-gray-800/50 flex items-center justify-between list-none">
          <span class="font-medium text-sm text-gray-200 uppercase tracking-wide">{{ family }}</span>
          <span class="text-gray-500 text-xs group-open:rotate-180 transition-transform">▼</span>
        </summary>
        <div class="border-t border-gray-800 overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-800">
                <th class="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Code</th>
                <th class="px-4 py-2.5 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Total</th>
                <th class="px-4 py-2.5 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Succeeded</th>
                <th class="px-4 py-2.5 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">ASR</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-800">
              {% for code, data in codes.items() %}
              <tr class="hover:bg-gray-800/30">
                <td class="px-4 py-2.5 font-mono text-xs text-gray-300">{{ code }}</td>
                <td class="px-4 py-2.5 text-right text-gray-400">{{ data.total }}</td>
                <td class="px-4 py-2.5 text-right text-red-400 font-medium">{{ data.succeeded }}</td>
                <td class="px-4 py-2.5 text-right">
                  <span class="font-bold
                    {% if data.asr > 0.5 %}text-red-400
                    {% elif data.asr > 0.2 %}text-amber-400
                    {% else %}text-green-400{% endif %}">
                    {{ data.asr | pct }}
                  </span>
                </td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </details>
      {% endif %}
      {% endfor %}
    </div>
  </div>
  {% endif %}

  <!-- Plugin × Strategy Heatmap -->
  {% if ctx.asr_heatmap %}
  <div class="mb-6">
    <h2 class="text-base font-semibold text-gray-200 mb-3">Plugin × Strategy Heatmap</h2>
    <div class="bg-gray-850 border border-gray-800 rounded-xl overflow-hidden overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-800">
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Plugin</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Strategy</th>
            <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Total</th>
            <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">ASR</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-800">
          {% for plugin_id, strategies in ctx.asr_heatmap.items() %}
          {% for strategy_id, data in strategies.items() %}
          <tr class="hover:bg-gray-800/30 transition-colors">
            <td class="px-4 py-3 font-mono text-xs text-gray-300">{{ plugin_id }}</td>
            <td class="px-4 py-3 text-xs text-gray-500">{{ strategy_id }}</td>
            <td class="px-4 py-3 text-right text-gray-400">{{ data.total }}</td>
            <td class="px-4 py-3 text-right">
              <span class="inline-block px-2 py-0.5 rounded text-xs font-bold
                {% if data.asr > 0.5 %}bg-red-900/60 text-red-300
                {% elif data.asr > 0.2 %}bg-amber-900/60 text-amber-300
                {% elif data.asr > 0 %}bg-yellow-900/60 text-yellow-300
                {% else %}bg-green-900/60 text-green-400{% endif %}">
                {{ data.asr | pct }}
              </span>
            </td>
          </tr>
          {% endfor %}
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
  {% endif %}

  <!-- Findings -->
  <div class="mb-6">
    <h2 class="text-base font-semibold text-gray-200 mb-3">
      Findings
      <span class="text-gray-500 font-normal">({{ ctx.findings | length }} attack{{ 's' if ctx.findings | length != 1 }} succeeded)</span>
    </h2>
    {% if ctx.findings %}
    <div class="space-y-2">
      {% for f in ctx.findings %}
      <details class="bg-gray-850 border rounded-xl overflow-hidden
        {% if f.severity == 'critical' %}border-red-800/60{% elif f.severity == 'high' %}border-amber-800/60{% else %}border-gray-800{% endif %}">
        <summary class="px-4 py-3 cursor-pointer select-none hover:bg-gray-800/40 flex items-center gap-3 list-none">
          <span class="text-xs px-2 py-0.5 rounded font-semibold
            {% if f.severity == 'critical' %}bg-red-900/50 text-red-300
            {% elif f.severity == 'high' %}bg-amber-900/50 text-amber-300
            {% elif f.severity == 'medium' %}bg-blue-900/50 text-blue-300
            {% else %}bg-gray-700 text-gray-400{% endif %}">
            {{ f.severity }}
          </span>
          <span class="font-mono text-xs text-gray-200 font-medium">{{ f.plugin_id }}</span>
          <span class="text-gray-500 text-xs">{{ f.strategy_id }}</span>
          {% if f.fidelity_label %}
          <span class="text-gray-600 text-xs ml-auto">{{ f.fidelity_label }}</span>
          {% endif %}
        </summary>
        <div class="border-t border-gray-800 px-4 py-4 space-y-3">
          <div>
            <div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Objective</div>
            <p class="text-sm text-gray-300">{{ f.objective }}</p>
          </div>
          {% if f.rationale %}
          <div>
            <div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Judge Rationale</div>
            <p class="text-sm text-gray-400 italic">{{ f.rationale }}</p>
          </div>
          {% endif %}
          {% if f.conversation_id %}
          <div class="text-xs text-gray-600 font-mono">conversation: {{ f.conversation_id }}</div>
          {% endif %}
        </div>
      </details>
      {% endfor %}
    </div>
    {% else %}
    <div class="bg-gray-850 border border-green-900/30 rounded-xl p-6 text-center">
      <div class="text-green-400 text-2xl mb-2">🛡</div>
      <div class="text-green-300 font-medium">No successful attacks</div>
      <div class="text-gray-500 text-sm mt-1">All attempts were defended</div>
    </div>
    {% endif %}
  </div>

  <!-- Sanity Flags -->
  {% if ctx.sanity_flags %}
  <div class="mb-6">
    <h2 class="text-base font-semibold text-gray-200 mb-3">⚠ Sanity Flags</h2>
    <div class="space-y-2">
      {% for flag in ctx.sanity_flags %}
      <div class="bg-amber-950/30 border border-amber-800/40 rounded-xl px-4 py-3 flex items-start gap-3">
        <span class="text-amber-400 text-sm flex-shrink-0">⚠</span>
        <div class="text-sm">
          <span class="text-amber-300 font-mono">{{ flag.plugin_id }}</span>
          <span class="text-gray-400 mx-2">—</span>
          <span class="text-gray-300">{{ flag.note }}</span>
          <span class="text-gray-500 ml-2">(ASR {{ flag.asr | pct }})</span>
        </div>
      </div>
      {% endfor %}
    </div>
  </div>
  {% endif %}

</div>

<style>
@media print {
  aside, .no-print { display: none !important; }
  body { background: white; }
  main { color: black; }
}
</style>
{% endblock %}
```

- [ ] **Step 2: Run tests**

```powershell
pyritpocvenv\Scripts\python.exe -m pytest tests/ -q
```

Expected: all tests still pass.

- [ ] **Step 3: Smoke-test the report page**

Start server in DEMO_MODE, launch a run, wait for completion, click "View Full Report →". Verify:
- Header with run ID, status pill, ASR badge
- Framework Scorecard section with collapsible families
- Heatmap table with color-coded ASR cells
- Findings accordion (or "No successful attacks" green card)
- Print CSS hides sidebar when printing

- [ ] **Step 4: Commit**

```powershell
git add agentic_redteam/web/templates/report.html
git commit -m "feat: report page — scorecard, heatmap, findings accordion, Dark Pro theme"
```

---

## Task 6: Rewrite runs.html + cleanup + final tests

**Files:**
- Modify: `agentic_redteam/web/templates/runs.html`
- Delete: `static/app.css`, `static/app.js`

- [ ] **Step 1: Rewrite runs.html**

Replace the full contents of `agentic_redteam/web/templates/runs.html`:

```html
{% extends "base.html" %}
{% block body %}
<div class="p-6 max-w-5xl mx-auto">

  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-2xl font-bold text-white">Run History</h1>
      <p class="text-gray-500 text-sm mt-1">All red-team runs, newest first</p>
    </div>
    <a href="/"
       class="bg-red-600 hover:bg-red-700 text-white font-medium px-4 py-2.5 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
      ⚡ New Run
    </a>
  </div>

  {% if rows %}
  <div class="bg-gray-850 border border-gray-800 rounded-xl overflow-hidden">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-gray-800">
          <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Run ID</th>
          <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
          <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Target</th>
          <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Results</th>
          <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">ASR</th>
          <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Requested by</th>
          <th class="px-4 py-3"></th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-800">
        {% for r in rows %}
        <tr class="hover:bg-gray-800/40 transition-colors group">
          <td class="px-4 py-3">
            <span class="font-mono text-xs text-gray-200 font-medium">{{ r.run_id }}</span>
          </td>
          <td class="px-4 py-3">
            <span class="text-xs px-2.5 py-1 rounded-full font-medium border
              {% if r.status == 'running' %}bg-amber-950 text-amber-300 border-amber-800
              {% elif r.status == 'completed' %}bg-blue-950 text-blue-300 border-blue-800
              {% elif r.status == 'stopped' %}bg-orange-950 text-orange-300 border-orange-800
              {% elif r.status == 'failed' %}bg-red-950 text-red-300 border-red-800
              {% else %}bg-gray-800 text-gray-400 border-gray-700{% endif %}">
              {{ r.status }}
            </span>
          </td>
          <td class="px-4 py-3">
            <span class="font-mono text-xs text-gray-400 truncate max-w-[140px] block">{{ r.target_endpoint or '—' }}</span>
          </td>
          <td class="px-4 py-3 text-right">
            <span class="text-gray-300">{{ r.succeeded }}</span>
            <span class="text-gray-600">/</span>
            <span class="text-gray-500">{{ r.total }}</span>
          </td>
          <td class="px-4 py-3 text-right">
            <div class="flex items-center justify-end gap-2">
              <div class="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <div class="h-full rounded-full
                  {% if r.asr > 0.5 %}bg-red-500{% elif r.asr > 0.2 %}bg-amber-500{% else %}bg-green-500{% endif %}"
                     style="width: {{ (r.asr * 100) | int }}%"></div>
              </div>
              <span class="text-xs font-medium w-10 text-right
                {% if r.asr > 0.5 %}text-red-400{% elif r.asr > 0.2 %}text-amber-400{% else %}text-green-400{% endif %}">
                {{ r.asr | pct }}
              </span>
            </div>
          </td>
          <td class="px-4 py-3 text-gray-500 text-xs">{{ r.requested_by or '—' }}</td>
          <td class="px-4 py-3 text-right">
            <a href="/runs/{{ r.run_id }}"
               class="text-xs text-gray-500 hover:text-red-400 font-medium transition-colors group-hover:text-gray-300">
              View →
            </a>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
  <div class="flex flex-col items-center justify-center py-24 text-center">
    <div class="text-5xl mb-4 opacity-30">⚡</div>
    <h2 class="text-lg font-medium text-gray-400">No runs yet</h2>
    <p class="text-gray-600 text-sm mt-1 mb-6">Start your first red-team run to see results here.</p>
    <a href="/"
       class="bg-red-600 hover:bg-red-700 text-white font-medium px-5 py-2.5 rounded-lg text-sm transition-colors">
      ⚡ Start a Run
    </a>
  </div>
  {% endif %}

</div>
{% endblock %}
```

- [ ] **Step 2: Delete old static files**

```powershell
Remove-Item static/app.css, static/app.js
```

- [ ] **Step 3: Run the full test suite**

```powershell
pyritpocvenv\Scripts\python.exe -m pytest tests/ -q
```

Expected: same pass count as before + 3 new wizard tests = (previous total + 3) passed, skips unchanged.

- [ ] **Step 4: Full smoke-test — all 4 pages**

Start server in DEMO_MODE, verify each page:

1. **http://localhost:8006/** — wizard loads, 6-step nav works, form submits, redirects to live view
2. **http://localhost:8006/runs** — run appears in table with status pill and ASR bar
3. **http://localhost:8006/runs/{id}** — live view with stats cards and feed
4. **http://localhost:8006/runs/{id}/report** — full report with scorecard, heatmap, findings

Verify in-container too:
```powershell
docker run --rm -p 8006:8006 -e PYTHONPATH=/work -e DEMO_MODE=1 -v "D:/CodeandLearn/Vamshi/Projects/pyrit:/work" -w /work --entrypoint python ghcr.io/vamshikadumuri/pyrit:0.13.0-v2 scripts/serve.py
```

- [ ] **Step 5: Run full test suite in container**

```powershell
docker run --rm --entrypoint python -e PYTHONPATH=/work -e DEMO_MODE=1 -v "D:/CodeandLearn/Vamshi/Projects/pyrit:/work" -w /work ghcr.io/vamshikadumuri/pyrit:0.13.0-v2 -m pytest -q
```

Expected: same container pass count as before + 3 new wizard tests.

- [ ] **Step 6: Final commit**

```powershell
git add agentic_redteam/web/templates/runs.html
git rm static/app.css static/app.js
git commit -m "feat: complete UI redesign — Dark Pro theme, htmx wizard, Tailwind CSS, remove old vanilla CSS/JS"
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ §1 Goal: htmx + Tailwind + Alpine committed as static files
- ✅ §2 Visual Design: Dark Pro palette used throughout (`gray-925`, `gray-900`, `red-500`, etc.)
- ✅ §3 Shell: Fixed sidebar in base.html, active nav highlighting via `current_path`
- ✅ §4 Wizard: Step list (Alpine state), htmx partials, 6 step templates, validation on steps 1 & 4
- ✅ §5 Live Run: SSE named events, `htmx-sse`, stats cards (Alpine), feed, run_finished banner
- ✅ §6 Report: Scorecard, heatmap, findings accordion, sanity flags, print CSS
- ✅ §7 Run History: Dark table, status pills, ASR inline bar, empty state
- ✅ §8 Static Assets: Task 1 downloads and commits all four files
- ✅ §9 Backend Changes: wizard routes in Task 3, SSE update in Task 4, render.py in Task 2
- ✅ §10 No-change items: backend logic, presenters, tests — all preserved

**Type/name consistency:**
- `_hidden_fields(data, current_n)` defined in Task 3 Step 3, used by `_wizard_ctx` throughout
- `_sse(event, html)` new signature defined in Task 4 Step 3, replaces old `_sse(d)` signature — both call sites updated in the same step
- `data-step` attribute on each step partial root div — read by Alpine `updateStep()` in wizard.html
- `data-run-event="execution_done"` and `data-status` on feed_row.html — read by Alpine stats listener in live.html
- `run_id` passed to `run_finished.html` — available in the SSE generator as the outer closure variable
