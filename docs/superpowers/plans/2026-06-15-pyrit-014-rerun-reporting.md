# Plan: PyRIT 0.14.0 Upgrade + Re-run + Enhanced Reporting

Spec: `docs/superpowers/specs/2026-06-15-pyrit-014-rerun-reporting-design.md`
Date: 2026-06-15
Branch: master (user explicitly consented)

---

## Task 1 — PyRIT 0.14.0: adapter.py `AttackExecutor` migration

**File:** `agentic_redteam/engine/adapter.py`

**Steps:**
1. Import `AttackExecutor` from `pyrit.executor.attack`
2. In `execute_plan()`, replace lines 97-102:
   ```python
   try:
       result = await attack.execute_async(objective=plan.objective, memory_labels=plan.labels)
   except TypeError:
       result = await attack.execute_async(objective=plan.objective)
   return result
   ```
   With:
   ```python
   executor = AttackExecutor()
   results = await executor.execute_attack_async(attack=attack, objectives=[plan.objective])
   return results.get_results()[0]
   ```
3. Remove the now-unused try/except block.

**Verify:** `pytest tests/ -x -q 2>&1 | head -30` — no import errors from adapter.

---

## Task 2 — PyRIT 0.14.0: scorer test mock fix

**File:** `tests/engine/test_scorer.py`

**Steps:**
1. Add `from unittest.mock import MagicMock` near the top of the file (after the pytest imports).
2. Replace every `object()` used as a judge target mock with `MagicMock()`:
   - `_scorer()` function (line 38): `PromptfooRubricScorer(MagicMock(), ...)`
   - `test_build_scorer_routes_by_rubric_kind` (line 73): `judge = MagicMock()`
   - `test_live_output_binding_uses_response_text` (line 90): `PromptfooRubricScorer(MagicMock(), ...)`
   - `test_build_scorer_dynamic_coding_is_insecure_code` (line 133): `MagicMock()`
   - `test_build_scorer_heuristic_is_selfask_not_substring` (line 144): `MagicMock()`

**Verify:** `pytest tests/engine/test_scorer.py -v 2>&1` — all 7 tests pass (they import-skip on non-PyRIT; in the container they would pass).

---

## Task 3 — PyRIT 0.14.0: memory_query.py `original_value` fix

**File:** `agentic_redteam/reports/memory_query.py`

**Steps:**
1. In `_extract_response_text()`, update the attribute probe list at line 54:
   ```python
   for attr in ("original_value", "text", "content", "value"):
   ```
   (add `"original_value"` as the first probe)
2. No other changes to this function.

**Verify:** `pytest tests/ -x -q 2>&1 | head -20`

---

## Task 4 — Re-run: `store.py` schema migration + persist request

**File:** `agentic_redteam/store.py`

**Steps:**
1. Add `request_json TEXT NOT NULL DEFAULT ''` column to `_SCHEMA` (in the `runs` table definition, after `config_json`).
2. In `_open()`, after `executescript(_SCHEMA)`, add migration for existing databases:
   ```python
   try:
       await self._conn.execute(
           "ALTER TABLE runs ADD COLUMN request_json TEXT NOT NULL DEFAULT ''"
       )
   except Exception:
       pass  # column already exists
   ```
   Place this before `await self._db.commit()`.
3. In `create_run()`, add `request_json` to the INSERT:
   - Add `"request_json"` to the column list in the INSERT statement
   - Add `request.model_dump_json()` to the VALUES tuple (after `config_json` value)

**Verify:** `pytest tests/ -x -q 2>&1 | head -30` — all existing store/manager/app tests still pass.

---

## Task 5 — Re-run: `runs.py` endpoint

**File:** `agentic_redteam/web/routes/runs.py`

**Steps:**
1. Add import: `from uuid import uuid4` (check if already present via utils import; if not, add it)
2. Add import: `from agentic_redteam.records import RunRequest` (check if already imported)
3. Add the endpoint after the existing `stop_run` route:

```python
@router.post("/{run_id}/rerun")
async def rerun_run(
    run_id: str,
    store: Annotated[Store, Depends(get_store)],
    manager: Annotated[RunManager, Depends(get_manager)],
) -> RedirectResponse:
    row = await store.get_run(run_id)
    if not row or not row.get("request_json"):
        return JSONResponse({"error": "No request data for this run"}, status_code=404)
    req = RunRequest.model_validate_json(row["request_json"])
    new_run_id = f"{run_id}_re_{uuid4().hex[:6]}"
    req.config.run_id = new_run_id
    manager.start(req)
    _log.info("Re-run %s created from %s", new_run_id, run_id)
    return RedirectResponse(f"/runs/{new_run_id}", status_code=303)
```

**Verify:** `pytest tests/web/test_app.py -v 2>&1` — existing tests pass; manually inspect endpoint signature.

---

## Task 6 — Re-run: UI buttons

**Files:** `agentic_redteam/web/templates/report.html`, `agentic_redteam/web/templates/live.html`

**Steps:**

In `report.html`, add a "Re-run" button to the header `<div class="flex gap-2 no-print">` section (alongside the JSON and Print buttons):
```html
<form method="post" action="/runs/{{ ctx.summary.run_id }}/rerun" class="inline">
  <button type="submit"
          class="border border-gray-700 hover:border-gray-600 text-gray-400 hover:text-white px-3 py-2 rounded-lg text-sm transition-colors inline-flex items-center gap-1.5">
    ↺ Re-run
  </button>
</form>
```

In `live.html`, add a "Re-run" button to the completed-run banner (inside the `{% if ctx.summary.status in ('completed', 'stopped') %}` block, alongside the "View Full Report" button):
```html
<form method="post" action="/runs/{{ run_id }}/rerun" class="inline">
  <button type="submit"
          class="border border-gray-700 hover:border-gray-600 text-gray-400 hover:text-white font-medium px-4 py-2 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
    ↺ Re-run
  </button>
</form>
```

**Verify:** Visual inspection — button appears in report header and completed run banner.

---

## Task 7 — Enhanced Reporting: `ExecutionRecord.conversation` field

**Files:** `agentic_redteam/records.py`, `agentic_redteam/reports/aggregation.py`

**Steps:**

In `records.py`:
1. Add field to `ExecutionRecord`:
   ```python
   conversation: list[dict] = Field(default_factory=list)
   ```
   Place after `error: str = ""`.
2. Add `conversation` parameter to `from_plan()`:
   ```python
   @classmethod
   def from_plan(cls, plan, *, status, ..., conversation=None, error=""):
       ...
       return cls(..., conversation=conversation or [], error=error)
   ```

In `aggregation.py`:
1. In `all_executions()`, add `"conversation": r.conversation` to the dict for each record.
2. In `findings()`, add `"conversation": r.conversation` to the dict for each succeeded record.

**Verify:** `pytest tests/ -x -q 2>&1 | head -30` — no regressions; `ExecutionRecord.model_validate_json(ExecutionRecord.from_plan(...).model_dump_json())` round-trips cleanly (existing serialization tests pass).

---

## Task 8 — Enhanced Reporting: `memory_query.py` conversation population

**File:** `agentic_redteam/reports/memory_query.py`

**Steps:**
1. Add `_get_conversation()` helper after `_extract_response_text()`:
   ```python
   def _get_conversation(conversation_id: str) -> list[dict]:
       if not conversation_id:
           return []
       try:
           from pyrit.memory import CentralMemory
           memory = CentralMemory.get_memory_instance()
           messages = memory.get_conversation(conversation_id=conversation_id)
           log = []
           for msg in messages:
               for piece in getattr(msg, "message_pieces", []):
                   content = getattr(piece, "original_value", "") or ""
                   role = str(getattr(piece, "role", "") or "")
                   if content:
                       log.append({"role": role, "content": content})
           return log
       except Exception:
           return []
   ```
2. In `_result_to_record()`, call `_get_conversation(conv_id)` and pass result:
   ```python
   conversation = _get_conversation(conv_id)
   return ExecutionRecord.from_plan(
       plan,
       ...,
       conversation=conversation,
   )
   ```

**Verify:** `pytest tests/ -x -q 2>&1 | head -20` — no regressions (function is PyRIT-only; test files skip where PyRIT unavailable).

---

## Task 9 — Enhanced Reporting: `report.html` conversation log display

**File:** `agentic_redteam/web/templates/report.html`

**Steps:**

1. In the "All Executions" table expanded row (inside the `{% if ex.response_text %}...{% endif %}` group), add after the existing `error` block:
   ```html
   {% if ex.conversation and ex.conversation | length > 1 %}
   <div x-show="open" class="mt-2 pt-2 border-t border-gray-800/50">
     <div class="text-xs text-gray-600 mb-1.5 uppercase tracking-wide">Conversation Log</div>
     <div class="space-y-1 max-h-48 overflow-y-auto">
       {% for turn in ex.conversation %}
       <div class="flex gap-2 text-xs">
         <span class="flex-shrink-0 font-semibold w-16 text-right
           {% if turn.role == 'user' %}text-blue-400
           {% elif turn.role == 'assistant' %}text-purple-400
           {% else %}text-gray-500{% endif %}">{{ turn.role }}</span>
         <span class="text-gray-400 leading-relaxed">{{ turn.content | truncate(200) }}</span>
       </div>
       {% endfor %}
     </div>
   </div>
   {% endif %}
   ```

2. In the "Findings" accordion detail (after the "Target Response" block), add:
   ```html
   {% if f.conversation and f.conversation | length > 1 %}
   <div>
     <div class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
       <span class="w-1.5 h-1.5 rounded-full bg-indigo-400 inline-block"></span>
       Conversation Log ({{ f.conversation | length }} turns)
     </div>
     <div class="space-y-1.5 bg-gray-900/50 rounded-lg px-3 py-2 border border-gray-800/50 max-h-64 overflow-y-auto">
       {% for turn in f.conversation %}
       <div class="flex gap-2 text-xs">
         <span class="flex-shrink-0 font-semibold w-20 text-right
           {% if turn.role == 'user' %}text-blue-400
           {% elif turn.role == 'assistant' %}text-purple-400
           {% else %}text-gray-500{% endif %}">{{ turn.role }}</span>
         <span class="text-gray-300 leading-relaxed">{{ turn.content }}</span>
       </div>
       {% endfor %}
     </div>
   </div>
   {% endif %}
   ```

**Verify:** Start dev server, navigate to a completed report — conversation log shows for multi-turn executions (shows nothing for single-turn where `conversation | length <= 1`).

---

## Final verification

After all tasks:
```
pytest tests/ -x -q
```

All tests pass (scorer tests skip on laptop where PyRIT unavailable; pass in container).

Commit with message:
```
feat: PyRIT 0.14.0 compat, re-run, and enhanced reporting

- adapter: use AttackExecutor.execute_attack_async() (0.14.0 API)
- memory_query: probe original_value first; populate conversation log
- scorer tests: MagicMock() instead of object() for target mocks
- store: request_json column for full RunRequest persistence + migration
- web: POST /runs/{id}/rerun endpoint + Re-run button on report/live
- records: conversation field on ExecutionRecord
- aggregation: conversation in all_executions + findings output
- report.html: collapsible conversation log per execution
```
