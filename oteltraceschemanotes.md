# OTel Trace — What It Must Carry for P3/P4 Behaviour Scoring

**Context:** Stock OpenTelemetry GenAI semconv gives you the *action*, but none of the *authorization context* the v3 P3/P4 trace predicates key off. So the trace = standard tool spans **+** a custom attribute namespace (`redteam.*`) for the authz/provenance fields. Without the custom fields, the cross-principal and injection predicates (BOLA, BFLA, RBAC, excessive-agency, indirect-injection, etc.) are ungradeable and every affected row returns UNSCORABLE.

---

## Comes free from GenAI semconv

Verify exact keys against the spec — the GenAI conventions are still experimental and the attribute names have been moving.

- `gen_ai.operation.name` → `event.type` (chat / execute_tool)
- `gen_ai.tool.name`, `gen_ai.tool.call.id` → `event.tool_name`
- tool-argument capture → `event.params`
- `gen_ai.usage.*_tokens` + span count/duration → reasoning-dos budget and `run.tool_budget` consumption
- span status → coarse success/error only

## Must add as custom attributes (`redteam.*`)

Without these, BOLA / BFLA / RBAC / excessive-agency / injection are ungradeable.

- `redteam.caller.role`, `.authenticated`, `.authorized_scope` (list), `.action_limits` (JSON string), `.allowed_tools` (list) — caller identity + policy bounds
- `redteam.object.owner` — the principal owning the touched resource; this **is** the BOLA test
- `redteam.side_effect` (bool) — did the step mutate state
- `redteam.result_status` = `success | denied | error` — stock span status can't distinguish *denied* from *errored*, and that distinction is the difference between a blocked attack and a broken one
- `redteam.event.source` = `user | tool_output | retrieved_doc | memory | peer_agent` — provenance; the single most important field for indirect-injection / cca / system-prompt-override, and OTel **cannot infer it** — BankBot must tag it at the point it consumes the content
- `redteam.run.user_mandate` (on root span) — goal-deviation baseline for goal-misalignment / hijacking
- `redteam.step` (explicit int) — don't make the scorer trust start-time ordering across async spans

---

## Two plumbing gotchas (the cost of the push model)

- **Correlation:** put `redteam.run_id` (= the PyRIT objective/turn id) on the root span and propagate it, so the scorer joins spans → the exact attack run. Without it an async collector hands you spans you can't attribute.
- **Flush timing:** force-flush (or query-with-retry by run_id) before scoring — a not-yet-exported trace reads as a false UNSCORABLE, which pollutes exactly the metric you're trying to keep honest.

## Span shape

- One **root span per run** (`run_id`, `user_mandate`, `tool_budget`, session caller).
- One **child span per step**.
- **Tool calls as their own `execute_tool` spans**, carrying the authz attrs + `object_owner` + `side_effect` + `result_status`.
- The scorer rebuilds the ordered event list by sorting spans within the `trace_id`.

## Type gotcha

OTel attribute values are primitives or arrays of primitives — `authorized_scope` as a string array is fine, but nested dicts (`action_limits`, `params`) must be JSON-serialized or flattened.
