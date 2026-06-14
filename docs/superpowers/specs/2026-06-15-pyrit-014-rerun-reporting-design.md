# Design: PyRIT 0.14.0 Upgrade + Re-run + Enhanced Reporting

Date: 2026-06-15

## Context

Three independent concerns addressed together:

1. **PyRIT 0.14.0 broke two APIs** used by the live engine: `attack.execute_async()` is gone (replaced by `AttackExecutor.execute_attack_async()`), and `SelfAskTrueFalseScorer`/`InsecureCodeScorer` now validate `target.configuration` — so `object()` test mocks fail.

2. **Re-run is missing**: the wizard form doesn't persist enough state to replay a run; `runs.config_json` stores only `RunConfig` (plugins/strategies), not the full `RunRequest` (target/judge/adversarial endpoints + credentials).

3. **Reporting gaps**: the user wants per-execution detail — objective (prompt), prompts sent, response received, and evaluation verdict — in a clean, readable format. For multi-turn attacks (Crescendo), the full conversation log from PyRIT memory is missing.

---

## A. PyRIT 0.14.0 Compatibility

### A1 — `adapter.py`: `AttackExecutor` migration

**Current (broken):**
```python
result = await attack.execute_async(objective=plan.objective, memory_labels=plan.labels)
```

**Fix:**
```python
from pyrit.executor.attack import AttackExecutor
executor = AttackExecutor()
results = await executor.execute_attack_async(attack=attack, objectives=[plan.objective])
result = results.get_results()[0]
```

The `AttackExecutor.execute_attack_async()` returns an `AttackExecutorResult`; `.get_results()` returns `list[AttackResult]`. We take `[0]` since we always pass exactly one objective.

### A2 — `memory_query.py`: `MessagePiece.original_value`

`_extract_response_text()` tries `text`, `content`, `value` attributes. PyRIT 0.14.0 uses `original_value` as the canonical text field on `MessagePiece`. Add it as the first probe:

```python
for attr in ("original_value", "text", "content", "value"):
```

### A3 — `tests/engine/test_scorer.py`: mock target fix

`SelfAskTrueFalseScorer` (and `InsecureCodeScorer`) in 0.14.0 call `target.configuration.ensure_can_handle(...)` (or similar) during `__init__`. The plain `object()` mock has no `.configuration` attribute → `AttributeError`.

Fix: replace all `object()` judge mocks with `MagicMock()` (from `unittest.mock`). `MagicMock` auto-creates any attribute chain, so `.configuration.ensure_can_handle()` succeeds without needing to know the exact PyRIT API.

---

## B1. Re-run Feature

### Schema change

Add `request_json TEXT NOT NULL DEFAULT ''` to the `runs` table. This column stores the full serialized `RunRequest` (target, judge, adversarial endpoints, plugins, strategies, profile, concurrency, requested_by).

Since `CREATE TABLE IF NOT EXISTS` won't add columns to existing tables, apply a migration in `_open()`:

```python
try:
    await db.execute("ALTER TABLE runs ADD COLUMN request_json TEXT NOT NULL DEFAULT ''")
except Exception:
    pass  # column already exists
```

### Store change

`create_run()` serializes and persists `request.model_dump_json()` into `request_json`.

### Endpoint

`POST /runs/{run_id}/rerun`:
1. Fetch `row["request_json"]` from store.
2. Parse back to `RunRequest.model_validate_json(...)`.
3. Assign a new `run_id` (pattern: `{original_id}_rerun_{hex8}`).
4. Update `req.config.run_id` with the new ID.
5. Call `manager.start(req)` → redirect 303 to `/runs/{new_run_id}`.
6. Return 404 if `request_json` is empty (old run without this column).

### UI

Add a "Re-run" button to `report.html` header (and the completed-run banner in `live.html`). The button is a small `<form method="post" action="/runs/{run_id}/rerun">` with a single submit button.

---

## B2. Enhanced Reporting

### Goal

Each execution entry in the report should clearly show:
- **Objective**: the attack prompt sent to the target
- **Conversation log**: the full turn-by-turn exchange (critical for multi-turn Crescendo)
- **Evaluation**: scorer verdict + judge rationale

The current report already shows `objective`, `response_text`, `rationale`, `score_value` in the expandable row. What's missing is the multi-turn conversation log.

### `ExecutionRecord.conversation` field

Add to `records.py`:
```python
conversation: list[dict] = Field(default_factory=list)
# Each entry: {"role": "user"|"assistant"|"system", "content": "..."}
```

This field is populated at execution time from PyRIT memory and persisted in `record_json` in SQLite. The store and report load it transparently.

### Population in `memory_query.py`

Add a helper `_get_conversation(conv_id: str) -> list[dict]` that:
1. Calls `CentralMemory.get_memory_instance()` and `.get_conversation(conversation_id=conv_id)`
2. Iterates `Message.message_pieces`, extracts `piece.role` and `piece.original_value`
3. Skips empty pieces; returns `[]` on any exception (graceful degradation)

Call it in `_result_to_record()` and pass to `ExecutionRecord.from_plan()`.

Add `conversation` parameter to `ExecutionRecord.from_plan()`:
```python
@classmethod
def from_plan(cls, plan, *, status, ..., conversation=None):
    return cls(..., conversation=conversation or [])
```

### `aggregation.py` changes

`all_executions()` and `findings()` include `"conversation": r.conversation` in the output dicts.

### Template update (`report.html`)

In the "All Executions" table expanded row, add a conversation log section (only shown when `ex.conversation` is non-empty):

```html
{% if ex.conversation %}
<div x-show="open">
  <div class="text-xs text-gray-600 uppercase tracking-wide mb-1">Conversation</div>
  {% for turn in ex.conversation %}
  <div class="mb-1">
    <span class="text-xs font-semibold {% if turn.role == 'user' %}text-blue-400{% else %}text-purple-400{% endif %}">{{ turn.role }}:</span>
    <span class="text-xs text-gray-400 ml-1">{{ turn.content }}</span>
  </div>
  {% endfor %}
</div>
{% endif %}
```

Similarly in the Findings accordion.

---

## Implementation Tasks

| # | File(s) | Change |
|---|---------|--------|
| 1 | `engine/adapter.py` | Use `AttackExecutor.execute_attack_async()` |
| 2 | `reports/memory_query.py` | Add `original_value` probe; add `_get_conversation()` |
| 3 | `tests/engine/test_scorer.py` | Replace `object()` mocks with `MagicMock()` |
| 4 | `store.py` | Add `request_json` column + migration + persist in `create_run()` |
| 5 | `web/routes/runs.py` | Add `POST /{run_id}/rerun` endpoint |
| 6 | `templates/report.html` + `live.html` | Re-run button |
| 7 | `records.py` | Add `conversation` field + `from_plan()` param |
| 8 | `reports/aggregation.py` | Include `conversation` in output dicts |
| 9 | `templates/report.html` | Show conversation log in execution detail |
