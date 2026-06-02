# PyRIT Agentic Red-Teaming POC — Session Context

> Handoff brief to bootstrap the next session. Last updated: 2026-06-02 (v3).

## What this is
Building a POC for **PyRIT-based AI red-teaming of agentic apps** (OWASP Agentic / LLM / API / MCP / MITRE ATLAS / NIST / EU AI Act) for a bank, replacing Garak. Airgapped network; internal OpenAI-compatible LLM gateway (claude/gemini). **Canonical env = org ghcr image `ghcr.io/vamshikadumuri/pyrit:0.13.0-v2`** — code runs INSIDE this container (mirrors office laptop); PyRIT not pip-installed. A working `crescendo.py` already runs (local vLLM Qwen attacker → org gateway target, `SelfAskTrueFalseScorer` judge). Deliverables: **web app** (self-service runs + reports) + **notebook** (manual). No uncensored attacker LLM yet → POC uses local vLLM.

## Status (2026-06-02)
**Spec v2 finalized. Plans 1a + 1b + 1c BUILT, reviewed (APPROVED), and CONTAINER-VERIFIED.** Laptop: **76 passed + 2 skipped** (`pyritpocvenv\Scripts\python.exe -m pytest -q`; scorer + adapter skipped — PyRIT not on laptop). **In `ghcr.io/vamshikadumuri/pyrit:0.13.0-v2` container: 86 passed, 1 skipped** (live smoke `test_crescendo_end_to_end_live` skipped — `RUN_LIVE` not set). Built subagent-driven (implementer per task + independent test re-runs + a final opus review per plan). Catalog: 157 plugins / 35 strategies / 10 presets, 146 runnable. Engine quality core done + verified: AppProfile, objective generation (grounding/diversity/dedup/top-up), rubric rendering (lenient ChainableUndefined; all 134 real rubrics render), grading + **polarity inversion**, PromptfooRubricScorer (real-API, subclasses TrueFalseScorer) + routing. **Plan 1c adds:** strategy_map (StrategySpec + combo validity + exemptions), trajectory (tool-call parsing + fidelity grading), labels (build_memory_labels), plan (family_bindings + RunConfig + AttackPlan + resolve), scorer (§7.6 fallback + live-output binding + per-family routing), adapter (build targets/attack/scorer + execute_plan), Crescendo smoke test (gated on `RUN_LIVE`). Next: write/execute **Plan 2** (orchestrator + run config + SQLite store + audit log + report queries).

### Plan 1c VERIFY results (container: 86 passed, 1 skipped)
- **All 5 attack class imports confirmed** from `pyrit.executor.attack`: `CrescendoAttack`, `RedTeamingAttack`, `PromptSendingAttack`, `TreeOfAttacksWithPruningAttack`, `RolePlayAttack` (+ `SkeletonKeyAttack`, `ManyShotJailbreakAttack`, `ContextComplianceAttack` referenced in adapter strategy map).
- **`_AttackScoringConfig` requires real `TrueFalseScorer`** — worked around with module-level aliases (`TrueFalseScorer = pyrit.score.TrueFalseScorer`) for testability; adapter imports guarded under `TYPE_CHECKING` / try-except for laptop runs.
- **`memory_labels=` kwarg on `execute_async`**: unknown whether officially supported — try/except `TypeError` fallback in place in `adapter.py`; will verify in Plan 2 when memory/label queries are needed.
- **Converter attachment on `PromptSendingAttack`**: NOT verified (not on Crescendo smoke path; deferred to Plan 2 when non-Crescendo attack paths are exercised).
- **Memory/label query API for reports** (`CentralMemory` accessor + `get_prompt_request_pieces` rename → `Message`/`MessagePiece`): NOT verified yet — deferred to Plan 2 orchestrator + report queries work.

### ⚠️ VERIFIED PyRIT 0.13.0-v2 API (from the container — use these in Plan 1c; the image API is NEWER than stock 0.13.0)
- **`Score`** is in **`pyrit.models`** (NOT `pyrit.score`). Required kwargs: `score_value:str, score_value_description:str, score_type, score_rationale:str, message_piece_id, scorer_class_identifier`; optional `score_category: list[str]` (a LIST now), `score_metadata`, `objective`. No `prompt_request_response_id`.
- **Message model renamed:** `PromptRequestResponse`→**`Message`**, `PromptRequestPiece`→**`MessagePiece`** (both in `pyrit.models`). `Message(message_pieces: Sequence[MessagePiece])`. `MessagePiece(role=, original_value=, original_value_data_type=, converted_value_data_type=, conversation_id=, prompt_target_identifier=, prompt_metadata=)`; read text via `piece.converted_value`.
- **Scorer ABC:** custom scorers subclass **`TrueFalseScorer`** (itself `Scorer`) and implement **`_build_identifier()`** (via `self._create_identifier(params=...)`) + **`_score_piece_async(self, message_piece, *, objective=None) -> list[Score]`**. Do NOT override `score_async` (concrete; takes a `Message`, dispatches per piece). `TrueFalseScorer.__init__(*, validator: ScorerPromptValidator, score_aggregator=...)`. Use `ScorerPromptValidator(supported_data_types=["text"])`.
- **Judge round-trip helper (reuse it):** `Scorer._score_value_with_llm(*, prompt_target, system_prompt, message_value, message_data_type, scored_prompt_id, category=, objective=, score_value_output_key="score_value", rationale_output_key="rationale", ...) -> UnvalidatedScore`. It sets the system prompt, sends a `Message`, parses JSON `{score_value, rationale, ...}` (configurable keys — we pass `pass`/`reason`), retries (`@pyrit_json_retry`). Then `unvalidated.to_score(score_value=..., score_type="true_false")`.
- **Target send:** `PromptChatTarget.send_prompt_async(message=<Message>)` (kw is `message=`, returns a list; text at `resp[0].message_pieces[i].converted_value` where data_type=="text"). `set_system_prompt(system_prompt=, conversation_id=, attack_identifier=)`.
- **Present in `pyrit.score`:** `Scorer, SubStringScorer(*, substring, categories=[...], text_matcher=, aggregator=, validator=), InsecureCodeScorer, SelfAskTrueFalseScorer, TrueFalseQuestion, TrueFalseInverterScorer(*, scorer, validator=)`. `Score` is NOT here.
- **Container run pattern (PowerShell, not git-bash — MSYS mangles `/work`):** `docker run --rm --entrypoint python -e PYTHONPATH=/work -v "D:/CodeandLearn/Vamshi/Projects/pyrit:/work" -w /work ghcr.io/vamshikadumuri/pyrit:0.13.0-v2 -m pytest -q`. The image ENTRYPOINT requires `PYTHONPATH`/PYRIT_MODE; override `--entrypoint`. The container venv (`/opt/venv`) has pyrit+pydantic+jinja2+pytest but **no pip** (can't `pip install -e .`; use PYTHONPATH=/work). Still VERIFY for 1c: `OpenAIChatTarget` ctor (crescendo.py confirms endpoint/api_key/model_name/temperature), the `*Attack` classes + `execute_async` signature, memory/label query API.

### Carry-forward items from the Plan 1a final review (address in later plans)
- **Plan 1c `strategy_map`:** special-case `basic` (it's a direct-send baseline; ingest currently labels its `kind="attack"` — metadata only, harmless until 1c). Populate the intentionally-empty `pyrit_class`/`converter_chain`/`needs`/`params`.
- **Plan 1b scorer:** for `shared_grader` plugins (`bias:*`/`pii:*`/`harmful:*`), the caller must pass `harm_category`/bias-attribute into `rubric_bindings` so the shared grader is specialized per subcategory (don't drop the per-plugin rubric text).
- **Plan 2/3 wizard:** `intent` and `policy` are `runnable=True` but need user-supplied goals/policy text — gate them on that input separately (dataset gating only covers the 11 dataset plugins).
- **Before shipping:** add README (docker pull/run for `ghcr.io/vamshikadumuri/pyrit:0.13.0-v2`, mounts, env, dataset-mirror dir) + promptfoo MIT attribution (spec §17).
- Minor/no-action: `RubricKind.dataset` enum value currently unused by ingest; `_col_index` would raise on a malformed cell ref (fine for this file).

### Carry-forward items from the Plan 1b final review (FIXED-now + for later plans)
- **FIXED in 1b (`fdb0e5f`):** rubric renderer now uses `ChainableUndefined` (+ undefined-safe `dump`) so `competitors`/`vlsu`-style attribute access on optional vars renders empty instead of crashing; regression test renders all 134 real rubrics.
- **Plan 1c `scorer`:** implement spec §7.6 second-failure fallback to `SelfAskTrueFalseScorer` (+ fidelity downgrade) — currently only parse→one-retry, then raises. This is the safety net for render/parse failures.
- **Plan 1c resolve/plan layer:** family-aware shared_grader binding injection — set `harm_category` from the `harmful:*` subcategory; bias:* rubrics use a *different* attribute (NOT harmCategory), so the injector must be family-aware.
- **Plan 1c scorer:** replace `SubStringScorer(substring="")` dynamic/heuristic placeholders with real per-family scorers; verify `InsecureCodeScorer`/`SubStringScorer` constructors in-container.
- **Plan 1b polish (or 1c):** harden `parse_verdict` degraded path (route pass-key-less JSON to retry; fix `pass: no` → currently mis-parses as pass=True; the bias is toward UNDER-reporting violations — the dangerous direction); add trailing-comma JSON tolerance + meta/imperative filters to `parse_objectives`.
- **Plan 2 (dedup):** slot-variation objectives (same template, different amount/account/role) over-collapse at trigram-Jaccard 0.65 (~0.66 for amount/account variants) — consider token-set Jaccard or length-aware threshold for bank/agentic targets.
- **Container:** resolve all 5 `# VERIFY` points in `scorer.py`, especially that `_ask` reads the assistant response piece from the correct index.

## Big pivot in v2 (vs v1)
v1 hand-authored a scoped ~10-plugin subset. **v2 makes `promptfoo_plugins_catalog_1.xlsx` the single source of truth** and is much broader:
- **Ingest all 157 plugins + framework-level presets + all 35 strategies** (each PyRIT-mapped + fidelity-rated) from the Excel. **No tiers** — uniform display; v1's authored overlay is dropped as a structural feature.
- **Run everything via the generic path:** generate-locally objective generation + a generic `PromptfooRubricScorer` rubric grader. Dataset plugins (11) are cataloged but **execution-gated** on the HF mirror being present (fail loudly).
- **Presets are framework-level** (owasp_llm, owasp_agentic, owasp_api, mitre_atlas, nist_ai_rmf, eu_ai_act, + collections foundation/guardrails_eval/mcp/default). Per-category codes retained on each plugin for **report rollups**.
- **UI (promptfoo-inspired):** pick a preset OR hand-pick plugins + a **valid** strategy/converter combo (fidelity badges ✓/⚠/✕, strategy-exempt plugins disabled).
- **Named quality priorities (user-emphasized):** (§6) objective **generation quality** and (§7) the **rubric grader adapter / scorers** — both have explicit TDD contracts.

## Key facts learned from the Excel (verified by reading the file)
- 4 sheets: Plugins (157), Presets (85 categories across 7 families + 4 collections), Strategy Map (35), About (provenance + a 2026-06-01 PyRIT-0.13.0 re-verification of all class-name mappings).
- Plugins: 144 Generative / 11 Dataset / 2 Config-required (`intent`, `policy`). Objective source: generate-locally (145 incl. policy) / dataset-rows (11) / intent-passthrough (1).
- Rubrics are **Nunjucks-flavored** templates: `{{purpose}}/{{prompt}}/{{output}}`, `{% if tools %}{{tool | dump}}`, `{% if entities and entities.length>0 %}`, `{{harmCategory}}`, `{{policy}}`, `{{goal}}`, `{{conversationTranscript}}`. **Polarity is inverted** vs PyRIT: promptfoo pass/1 = SAFE, fail/0 = VIOLATION → must invert (TrueFalseInverterScorer / invert flag). #1 ASR bug.
- Some rubric cells are `[Dynamic rubric]` (coding-agent:*, agentic:memory-poisoning) or `[No static rubric]` (some datasets) → route to InsecureCodeScorer / SubStringScorer / heuristic.
- About-sheet PyRIT notes: orchestrators→`*Attack`; **no PAIRAttack**; `cca` plugin↔`ContextComplianceAttack`; `mischievous-user`↔`RolePlayAttack`; `jailbreak-templates`↔TextJailbreakConverter/SkeletonKeyAttack/ManyShotJailbreakAttack; `jailbreak:tree`↔TreeOfAttacksWithPruningAttack; encodings have drop-in converters. `OpenAIChatTarget` endpoint+api_key optional. Avoid Azure cloud scorers (airgap).

## Files
| File | What |
|---|---|
| `promptfoo_plugins_catalog_1.xlsx` | **The catalog (source of truth)** — 4 sheets. 114 KB. |
| `docs/superpowers/specs/2026-05-31-pyrit-agentic-redteam-poc-design.md` | **Design spec v2** (20 sections). §6 generation + §7 rubric scorer are the deep, quality-critical sections. |
| `docs/superpowers/plans/2026-06-01-plan-1a-catalog-foundation.md` | **Plan 1a (ready to execute).** Stdlib xlsx ingest → all 157 plugins / 35 strategies / 10 framework presets as committed JSON; Pydantic models; grouping; validating loader. Pure Python, no PyRIT — runs/tests anywhere. |
| `docs/superpowers/plans/2026-06-01-plan-1b-generation-and-grading.md` | **Plan 1b (ready after 1a).** The quality core: AppProfile, objective generation (grounding/diversity/dedup/top-up), rubric rendering (Nunjucks→Jinja2), grading + **polarity inversion**, PromptfooRubricScorer. Pure logic PyRIT-free + mock-tested; only `scorer.py` needs the container. |
| `docs/superpowers/plans/2026-05-31-engine-catalog-foundation.md` | **SUPERSEDED** (v1, scoped 10-plugin). Banner added; kept for history. |
| `docs/superpowers/plans/2026-06-02-plan-1c-engine-adapter.md` | **Plan 1c (BUILT + VERIFIED).** strategy_map + trajectory + labels + resolve→AttackPlan + PyRIT adapter + Crescendo smoke. |
| `docs/superpowers/plans/` (TODO) | **Plan 2** (orchestrator+store+reports), **Plan 3** (web), **Plan 4** (notebook). |
| `scripts/dump_xlsx.py` | **(built, works)** stdlib-only xlsx→tsv reader. Ingestion (`ingest/ingest_catalog.py`) will reuse this approach (no pandas/openpyxl available/airgapped). |
| `docs/_catalog_dump/*.tsv` | Inspection dump of the 4 sheets (Plugins/Presets/StrategyMap/About) — handy reference during implementation. |
| `claude_code_implementation_prompt.md` | Reference brief that informed v2 (full-catalog ingest, generic rubric adapter, generate-locally, strategy-map factory, polarity, dataset mirroring). |
| `crescendo.py`, `CLAUDE.md`, `initial_prompt.txt`, `pyritpocvenv/` | pre-existing |

## Plan roadmap (to be re-cut by writing-plans)
1a. Catalog: ingest Excel → models + loader + grouping + presets (157/35/presets) → validation.
1b. Engine core: App-Profile, **objective generation (§6)**, **rubric scorer + routing + polarity (§7)**, strategy-map factory + fidelity/exemptions, trajectory/fidelity, labels, resolve()→AttackPlan, PyRIT adapter (Crescendo end-to-end), DuckDB smoke.
2. Orchestrator + run config + SQLite store + audit log + report queries.
3. Web app (FastAPI + HTMX wizard: preset OR plugins+valid combo, SSE live view, reports/export).
4. Notebook parity.

## Verify-in-container points remaining (Plan 1c → carry-forwards for Plan 2)
~~`execute_async` signature~~ (confirmed, works), ~~`*Attack` class imports~~ (all 5 confirmed from `pyrit.executor.attack`), ~~scorer API~~ (verified in Plan 1b/1c — see VERIFIED block above). **Still open for Plan 2:**
- `memory_labels=` kwarg on `execute_async`: try/except TypeError fallback in place — verify proper API when implementing memory/label queries in Plan 2.
- Converter attachment on `PromptSendingAttack`: not on Crescendo smoke path — verify when Plan 2 exercises non-Crescendo attack strategies.
- Memory/label query API for reports: `CentralMemory` accessor + filter-by-labels pattern (note Message/MessagePiece rename may affect `get_prompt_request_pieces`) — verify in Plan 2 report queries.

## How to resume (cold start after a context clear)
1. Read THIS file top-to-bottom, then skim the spec `docs/superpowers/specs/2026-05-31-pyrit-agentic-redteam-poc-design.md` (§6 generation, §7 scorer) and the built plans `docs/superpowers/plans/2026-06-01-plan-1a-...md` + `...-plan-1b-...md` + `...-plan-1c-...md`.
2. Sanity-check the build: `pyritpocvenv\Scripts\python.exe -m pytest -q` (expect 76 passed, 2 skipped). Container full run: see the "Container run pattern" above (expect 86 passed, 1 skipped).
3. **Next work = write + execute Plan 2** (orchestrator + run config + SQLite store + audit log + report queries). Invoke **superpowers:writing-plans** to author `docs/superpowers/plans/2026-06-02-plan-2-orchestrator.md`. Key carry-forwards: verify `memory_labels=` kwarg + converter attachment on `PromptSendingAttack` + memory/label query API (see "Verify-in-container points" above). **Use the VERIFIED PyRIT 0.13.0-v2 API block above — do not re-guess class names.**
4. To revisit design decisions, see the spec's §20 decisions log.
