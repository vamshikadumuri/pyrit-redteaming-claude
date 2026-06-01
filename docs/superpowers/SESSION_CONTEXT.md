# PyRIT Agentic Red-Teaming POC — Session Context

> Handoff brief to bootstrap the next session. Last updated: 2026-06-01 (v2).

## What this is
Building a POC for **PyRIT-based AI red-teaming of agentic apps** (OWASP Agentic / LLM / API / MCP / MITRE ATLAS / NIST / EU AI Act) for a bank, replacing Garak. Airgapped network; internal OpenAI-compatible LLM gateway (claude/gemini). **Canonical env = org ghcr image `ghcr.io/vamshikadumuri/pyrit:0.13.0-v2`** — code runs INSIDE this container (mirrors office laptop); PyRIT not pip-installed. A working `crescendo.py` already runs (local vLLM Qwen attacker → org gateway target, `SelfAskTrueFalseScorer` judge). Deliverables: **web app** (self-service runs + reports) + **notebook** (manual). No uncensored attacker LLM yet → POC uses local vLLM.

## Status (2026-06-01)
**Spec v2 finalized. Plans 1a + 1b written. No code generated yet.** Git not yet initialized (Plan 1a Task 0 does `git init`). Next: write Plan 1c (engine wiring + PyRIT adapter), then execute. Awaiting user choice on execution mode (subagent-driven vs inline).

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
| `docs/superpowers/plans/` (TODO) | **Plan 1c** (strategy_map + trajectory + labels + resolve→AttackPlan + PyRIT adapter + Crescendo smoke), then **Plan 2** (orchestrator+store+reports), **Plan 3** (web), **Plan 4** (notebook). |
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

## Verify-on-PyRIT-machine points (0.13.0)
`execute_async(memory_labels=...)`; constructor signatures for `CrescendoAttack`/`RedTeamingAttack`/`PromptSendingAttack`/`TreeOfAttacksWithPruningAttack`/`RolePlayAttack`/`SkeletonKeyAttack`/`ManyShotJailbreakAttack`/`ContextComplianceAttack`; converter class names; scorer classes (`SelfAskTrueFalseScorer`, `SelfAskLikertScorer`, `TrueFalseInverterScorer`, `SubStringScorer`, `InsecureCodeScorer`); `CentralMemory.get_memory_instance()` / `get_prompt_request_pieces(labels=...)`.

## How to resume
The user is reviewing spec v2. If approved → invoke **superpowers:writing-plans** to rewrite the implementation plan (emphasize TDD on §6 generation contracts and §7 scorer polarity/routing). To revisit design, see the spec's §20 decisions log.
