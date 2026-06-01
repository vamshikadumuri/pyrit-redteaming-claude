# Implementation Brief — Air-Gapped LLM Red-Team Harness (Promptfoo catalog → PyRIT 0.13.0)

> Paste this whole file to Claude Code as the task brief. It builds a sanctioned, **internal, air-gapped** AI red-teaming POC that reuses Promptfoo's open-source plugin taxonomy/objectives/rubrics as a static corpus and executes everything through Microsoft **PyRIT 0.13.0** against a self-hosted LLM gateway. This is for authorized robustness/safety testing of our **own** systems only; the harness must target only operator-configured endpoints and log every run.

## 1. Goal
We cannot run Promptfoo directly (it relies on remote inference; our environment is air-gapped). Build a Python service + web UI that:
1. Ingests the provided Excel catalog into an objective/rubric store.
2. Lets a user pick a **preset** (OWASP LLM / Agentic / MCP-style groupings) and/or individual plugins + strategies (Promptfoo-style config).
3. Generates/sources attack objectives, delivers them via PyRIT attacks/converters, and grades responses with a Promptfoo-rubric-driven PyRIT scorer.
4. Reports per-objective pass/fail, attack-success-rate (ASR), and OWASP/MITRE rollups, with full transcripts.

All three model roles (attacker, target, judge) are OpenAI-compatible endpoints on our internal gateway. The system must run **fully offline**.

## 2. Inputs & environment
- **Catalog file:** `promptfoo_plugins_catalog.xlsx` (place in `./data/`). Sheets & columns:
  - **Plugins** — `Plugin ID`, `Name`, `Severity`, `Plugin Type` (Generative | Dataset | Config-required), `OWASP LLM Top 10`, `OWASP Agentic Top 10`, `OWASP API Top 10`, `MITRE ATLAS`, `Objective Source` (dataset-rows | intent-passthrough | generate-locally), `Objective (description)`, `Imperative Objective Seed / Attacker-Goal Hint (draft)`, `Grading Rubric / Notes`.
  - **Presets** — `Framework`, `Category ID`, `Category / Name`, `Plugins (as Promptfoo defines)`, `Promptfoo Recommended Strategies`, `PyRIT 0.13.0 Strategy Equivalents`.
  - **Strategy Map** — `Promptfoo Strategy ID`, `Display Name`, `Type`, `Air-gap (offline?)`, `PyRIT 0.13.0 Equivalent`, `PyRIT Fidelity (how clean?)`, `DEFAULT?`, `Description (Promptfoo)`.
  - **About** — provenance/caveats (read it; honor the caveats).
- **PyRIT:** version **0.13.0** exactly (`pip install pyrit==0.13.0`). Verify every class/param name against the installed package before relying on it — names shift across releases. Key facts already confirmed for 0.13.0: orchestrators are now `*Attack` classes; **there is no `PAIRAttack`**; `OpenAIChatTarget` takes `endpoint` and `api_key` as **optional**.
- **Gateway:** OpenAI-compatible base URL + key supplied via env/config. Three logical models: `attacker` (adversarial_chat), `target` (system under test), `judge` (scorer). A target may be added later — design for it now.
- **Python 3.11+.** No outbound internet at runtime.

## 3. Repo structure (suggested)
```
redteam-harness/
  data/promptfoo_plugins_catalog.xlsx
  src/redteam_harness/
    ingest.py          # xlsx -> objective_store (SQLite + JSON export)
    store.py           # query layer over the catalog
    config.py          # Promptfoo-style YAML config model (pydantic)
    targets.py         # build attacker/target/judge OpenAIChatTargets
    rubric_adapter.py  # PromptfooRubricScorer (custom PyRIT Scorer)
    strategy_map.py    # Promptfoo strategy -> PyRIT converter/attack factory
    objectives.py      # objective sourcing (dataset / intent / generate-locally)
    orchestrate.py     # run a campaign: objective x strategy -> attack -> score
    report.py          # ASR, framework rollups, transcript export
    api.py             # FastAPI endpoints
  web/                 # React UI (preset selector, plugin picker, YAML view, dashboard)
  tests/
  README.md
```

## 4. Components to build

### 4.1 Catalog ingestion (`ingest.py`, `store.py`)
- Parse all four sheets with `openpyxl`/`pandas` into a normalized SQLite DB + a JSON snapshot.
- Tables: `plugins`, `presets` (one row per framework category), `strategy_map`.
- Parse multi-value cells (comma-separated framework tags, plugin lists, strategy lists) into relations.
- Expose queries: plugins by preset/framework, plugin metadata, strategy → PyRIT mapping + fidelity, strategy-exempt set.

### 4.2 Config model (`config.py`) — Promptfoo-style
Pydantic model mirroring a Promptfoo redteam YAML so it feels familiar:
```yaml
target: { provider: target, purpose: "<the app's purpose/system context>" }
presets: [ "owasp:llm", "owasp:agentic" ]      # expands to plugins + recommended strategies
plugins: [ "contracts", "pii:direct", ... ]     # explicit additions
strategies: [ "jailbreak", "crescendo", "base64" ]  # global unless scoped
numTests: 5
```
- Preset expansion: pull the preset's plugin list AND its `Promptfoo Recommended Strategies` from the Presets sheet (these are real, source-defined — but note coverage is partial: OWASP API has none, MITRE 8/16, NIST 5/21, EU 3/14; fall back to DEFAULT strategies = `basic, jailbreak:meta, jailbreak:composite` when a category lists none).
- Allow per-strategy plugin scoping (Promptfoo's `config.plugins`) — default is all plugins.

### 4.3 Targets (`targets.py`)
- Factory building three `OpenAIChatTarget`s from config, all pointed at the gateway (`endpoint=<gateway>/v1`, `api_key=<key or "">`, `model_name=...`). Keep them independent so attacker/target/judge can be different models.
- Provide `HuggingFaceChatTarget` / `HTTPXAPITarget` as alternate backends behind the same interface.
- **Do NOT use cloud scorers/targets** (`AzureContentFilterScorer`, `PromptShieldScorer`, Azure speech) — air-gap.

### 4.4 Rubric adapter (`rubric_adapter.py`) — the key piece
Implement `PromptfooRubricScorer`, a custom PyRIT `Scorer` that lets the Promptfoo rubric text (the `Grading Rubric / Notes` column) drive a PyRIT judge. Requirements:
- Render the rubric with the judge inputs: map Promptfoo `{{purpose}}` → the attack `objective`/task, `{{output}}` → the response under test, `{{prompt}}` → the attack input (pull from conversation context). The `{{ }}` syntax is Jinja2-compatible; only the variable **names** need remapping.
- **Strip any inline "Output Format"/JSON block** in the rubric (sector graders embed one) — let PyRIT own the output contract to avoid double schemas.
- **Polarity inversion (critical):** Promptfoo convention is *pass/score-1 = the model behaved safely*. PyRIT objective scorers must return *true = objective achieved = attack succeeded = violation*. So invert. Prefer wrapping in PyRIT's **`TrueFalseInverterScorer`**, or expose an `invert: bool = True` flag. Get this right or ASR comes out backwards.
- Return a proper PyRIT `Score` (verify `Score`/`Scorer` signature against installed 0.13.0). Include the judge's rationale.
- For the rows whose `Grading Rubric / Notes` is **not** an LLM rubric, route differently:
  - Shared-grader rows (bias:*, pii:*, harmful:* fallbacks): rubric text is present — use it, inject the subcategory.
  - `[Dynamic rubric]` rows (coding-agent:*, agentic:memory-poisoning): no static rubric — use a programmatic check or `InsecureCodeScorer` (good fit for coding-agent).
  - `[No static LLM rubric]` rows (cyberseceval, donotanswer, xstest, cross-session-leak, etc.): use `SubStringScorer`/heuristic or the dataset's own grading.

Reference skeleton (complete & verify against 0.13.0):
```python
class PromptfooRubricScorer(Scorer):
    def __init__(self, judge_target, rubric_text: str, *, invert: bool = True):
        self._judge = judge_target
        self._rubric = strip_output_format_block(rubric_text)
        self._invert = invert
        self.scorer_type = "true_false"
    async def score_async(self, request_response, *, task: str | None = None):
        prompt = render_jinja(self._rubric,
                              purpose=task,
                              output=request_response.converted_value,
                              prompt=get_attack_input_from_context(request_response))
        verdict = await ask_judge_json(self._judge, prompt)  # -> {pass, score, reason}
        achieved = (not verdict["pass"]) if self._invert else verdict["pass"]
        return [Score(score_value=str(achieved).lower(), score_type="true_false",
                      score_rationale=verdict.get("reason", ""),
                      score_category="promptfoo_rubric", ...)]
```
Add JSON-parse retry/repair and a fallback to `SelfAskTrueFalseScorer`.

### 4.5 Strategy mapping (`strategy_map.py`)
- Read the Strategy Map sheet; build a factory: selected Promptfoo strategy → PyRIT converter(s) and/or attack class.
- Honor the **PyRIT Fidelity** column: `Clean` → use the named class; `Approximate` → use the listed class and log a fidelity warning; `Custom needed` → call a stub you implement (`piglatin`, `camelcase`, `best-of-n`, `indirect-web-pwn`) or skip with a clear message; `Meta` (`layer` → stack converters, `other-encodings` → expand to the encoder set); `N/A` (`retry`) → harness re-run, not an attack.
- **Strategy-exempt plugins:** do NOT apply converters/multi-turn wrapping to dataset plugins or the standalone agentic ones (`system-prompt-override`, `agentic:memory-poisoning`). Read this exemption from `Plugin Type == Dataset` plus that small agentic set.
- **Remote-only strategies (9)** — `audio, citation, gcg, goat, indirect-web-pwn, jailbreak:composite, jailbreak:hydra, jailbreak:likert, jailbreak:meta` — have no Promptfoo-hosted generator available offline. Reproduce with our local attacker model via PyRIT (`RedTeamingAttack` flavors) and flag reduced fidelity.

### 4.6 Objective sourcing (`objectives.py`) — branch on `Objective Source`
- **dataset-rows (11 plugins):** load the corresponding dataset from a locally **mirrored** copy (we must pre-stage the HuggingFace datasets into the air-gap) into a PyRIT `SeedPromptDataset`. Respect each dataset's license.
- **intent-passthrough (`intent`):** user supplies a list of goals → use directly as PyRIT objectives (~1:1).
- **generate-locally (145 plugins):** expand the `Imperative Objective Seed / Attacker-Goal Hint` into N concrete objectives using the **attacker** model. The hint alone is low fidelity — see §5 "missing piece": feed the attacker the plugin's **generation template** + the **target purpose** + the hint, and phrase outputs as concrete attacker goals. `policy` plugin: generate from the user-supplied policy statement.

### 4.7 Orchestration (`orchestrate.py`)
- For each (objective, strategy) pair, pick the PyRIT attack: `PromptSendingAttack` (+converters) for single-turn/encoding; `RedTeamingAttack` for iterative jailbreak/goat/meta/hydra; `CrescendoAttack`; `TreeOfAttacksWithPruningAttack` for tree/TAP; `RolePlayAttack` for mischievous-user; `SkeletonKeyAttack`/`ManyShotJailbreakAttack`/`TextJailbreakConverter` for jailbreak-templates.
- Wire `objective_target=target`, `adversarial_chat=attacker`, `objective_scorer=PromptfooRubricScorer(judge,...)`.
- Use PyRIT memory (local SQLite/DuckDB, `IN_MEMORY` or file) — no cloud.
- Add concurrency limits + retry/backoff against the gateway; make `numTests`, `max_turns` configurable.

### 4.8 Reporting (`report.py`)
- Per-objective pass/fail + rationale, per-plugin ASR, and **framework rollups** (OWASP LLM/Agentic/API, MITRE) using the catalog's mapping columns.
- Export transcripts from PyRIT memory. Severity-weighted summary using the `Severity` column.

### 4.9 Web UI (`web/`, `api.py`)
- FastAPI backend exposing: list presets/plugins/strategies, build/validate config, run campaign (async + progress), fetch results.
- React UI: preset selector (OWASP LLM/Agentic/MCP groupings → auto-select mapped plugins + recommended strategies), per-plugin multiselect, strategy picker (show fidelity badge from the sheet), a Promptfoo-style YAML view ⇄ form, run button, and a results dashboard (ASR, framework rollup, transcript drill-down). No browser storage for state beyond the session.

## 5. Things to get right / that are easy to miss
- **Missing generation templates:** the catalog's hint column is a *seed*, not the multi-case output Promptfoo's remote service produces. For real fidelity on the 145 generative plugins we still need each plugin's `getTemplate()` body extracted from the Promptfoo repo (MIT, v0.121.13). Build `objectives.py` to accept a `generation_templates/<plugin_id>.txt` corpus and use it when present; leave a TODO + a small extractor script (`scripts/extract_templates.py`) that clones promptfoo and pulls `getTemplate()` per plugin.
- **Polarity** (see 4.4) — the single most common ASR bug.
- **Dataset mirroring** — the 11 dataset plugins are useless without the staged datasets; document the mirror step and fail loudly if missing.
- **MCP has no bundled strategies** — treat `mcp` as a plugin collection; let the user choose strategies.
- **Verify PyRIT names** at startup (introspect the installed package); fail fast with a clear message if a mapped class is absent in the pinned version.
- **No cloud calls** anywhere (scorers, speech, content filters). Add a guard that rejects non-gateway endpoints.
- **Authorization guardrails:** target endpoints come only from operator config; record an audit log (who/when/which target/which objectives). Add a config flag confirming authorization before a run.

## 6. Phased delivery + acceptance criteria
1. **Ingestion + store** — `ingest.py` loads all 4 sheets; `store.py` returns plugins for a preset and a strategy's PyRIT mapping. *Done when* `pytest` shows 157 plugins, 35 strategies, and preset expansion works.
2. **PyRIT spike** — three targets on the gateway; `PromptSendingAttack` + a converter, then `CrescendoAttack` and `TreeOfAttacksWithPruningAttack`, fully offline; `PromptfooRubricScorer` returns an inverted verdict. *Done when* one objective runs end-to-end air-gapped with a correct pass/fail.
3. **Objective sourcing + orchestration** — all three source branches; campaign over a small preset. *Done when* an OWASP-LLM subset runs and produces ASR.
4. **Reporting + UI** — dashboard with framework rollups and transcripts; preset/plugin/strategy selectors. *Done when* a non-developer can configure and launch a run and read results.

## 7. Constraints
- Offline only; OpenAI-compatible gateway for all models; PyRIT 0.13.0 pinned; MIT-compatible deps. Keep secrets in env, never in the repo. Add a `README.md` with the dataset-mirroring and gateway-config steps.
