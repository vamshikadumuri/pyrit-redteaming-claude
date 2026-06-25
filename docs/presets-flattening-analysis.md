# Presets: requirement, analysis, and the resulting plan

## 1. Your requirement (verbatim)

> "Where is per-category rows + plugins needed? On promptfoo UI I can see users can select
> preset (that displays what all plugins are selected) and then when they hit next it shows
> recommended strategies of promptfoo. I just need to have all promptfoo taxonomy plugins per
> preset and recommended promptfoo strategies (as per promptfoo code/data). I agree on the
> strategy map which can be picked from that corresponding sheet."

> "Then my question would be how promptfoo is presenting to test this? I can only see in their
> UI that it allows users to choose the preset itself that bundles all the plugins and then
> recommends strategy? How does this recommendation show up? Does it mean there is no real use
> of per category mapping in the frameworks.ts that's used on the Promptfoo UI. If yes, there is
> no utilization of it on promptfoo UI, I would just rather have preset, plugin list and
> recommended strategies (I hope promptfoo has recommendations per preset too). Also **don't
> tinker the per category sheet as it faithful already and create a new sheet for the same** if
> you agree on the above."

**In short:** present presets as a flat `preset → {plugin list, recommended strategies}`. Keep the
per-category sheet untouched (it is a faithful promptfoo mirror). Put the flat view in a *new*
sheet. Strategy→PyRIT resolution continues to come from the "Strategy Map" sheet.

## 2. Latest analysis / findings

**(a) promptfoo flattens per-category to preset level — the category split never reaches a run.**
Tracing promptfoo's `synthesize()` → `expandPlugin(plugin, mapping)` in `src/redteam/index.ts`:
for a selected framework it reads **both** `mapping.plugins` and `mapping.strategies` from each
sub-category in `frameworks.ts` and pushes them into one run config (a union). The UI's "next →
recommended strategies" step shows that union, not a per-category breakdown. So the per-category
`{plugins, strategies}` rows are an *authoring/source* structure; what actually gets tested is the
deduped preset-level union.

**(b) `category_index` in our catalog is dead structure.** It is built by the ingest
(`ingest_catalog.py` `build_presets`), declared on the `Preset` model (`catalog/models.py:106`),
and asserted in two tests — but **consumed nowhere** at runtime/UI/report. The app only ever reads
the flat `preset.plugins` and `preset.recommended_strategies`
(`web/presenters.py:58-59`, `web/utils.py:98-99`).

**(c) Therefore a preset-level `{plugins, recommended_strategies}` model is exactly promptfoo's
consumed model** — your requested shape. The per-category detail is only useful for (i) faithful
re-extraction from promptfoo and (ii) a compliance/coverage report, not for driving runs.

**(d) Side finding — exempt-plugin silent drop.** OWASP Agentic's recommended strategies omit
`basic`, yet `system-prompt-override` and `agentic:memory-poisoning` are `strategy_exempt` (they
only run with `basic`). So `plan.resolve()` drops them and the preset silently tests nothing for
those plugins. Best fixed in routing (`engine/plan.py:resolve()`), not in the data, so presets stay
faithful. `combo_supported()` in `engine/strategy_map.py:103-108` already encodes the exempt rule.

## 3. Open decision (needs your call before execution)

The new flat sheet can play one of two roles:

- **Hand-editable source** — add a `Preset Bundles` sheet, seed it once from the per-category
  union, then edit by hand; ingest reads it. Gives per-preset control; risks drift from the
  per-category sheet on re-extraction.
- **Auto-derived view** — per-category sheet stays the single source of truth; ingest keeps
  deriving the union (as today) and the flat sheet is emitted as a generated artifact, not
  consumed. No drift; one-sheet re-extraction.

## 4. Resulting plan (proposed — not yet executed)

### 4.1 Workbook (`promptfoo_plugins_catalog_enriched.xlsx`)
- Leave the per-category "Presets" sheet **untouched** (faithful promptfoo mirror).
- Add a flat sheet `Preset Bundles`, one row per preset:
  `Preset ID | Framework | Title | Plugins | Recommended Strategies`, seeded from the deduped
  per-category union (so it starts faithful).

### 4.2 Ingest (`agentic_redteam/ingest/ingest_catalog.py`)
- Point preset building at the flat sheet (`write_catalog`, ~line 254) **or** keep reading the
  per-category sheet and emit the flat view — depending on the §3 decision.
- Simplify `build_presets` (lines 199-244) to one row per preset: split `Plugins`
  (reuse `_split_list` + `_expand_plugins`), split `Recommended Strategies` (keep the
  `s in all_strategy_ids` filter), **drop all `category_index` logic** and the per-category
  `ensure`/accumulation machinery. Keep `_DEFAULT_STRATEGIES` as the empty-cell fallback.

### 4.3 Model (`agentic_redteam/catalog/models.py`)
- Remove `category_index: dict[str, list[str]]` from `Preset` (line 106).

### 4.4 Tests
- `tests/ingest/test_ingest_catalog.py:97` — drop the `category_index` assertion; assert the flat
  preset's expected `plugins` + `recommended_strategies` instead.
- `tests/catalog/test_models.py:62` — remove the `category_index == {}` check.

### 4.5 (Recommended, optional) Fix the exempt-plugin silent drop
In `engine/plan.py:resolve()`, ensure every `strategy_exempt` plugin always gets a `basic` pass
regardless of the preset's strategy list (routing fix; presets stay faithful).

## 5. Verification
1. Re-run ingest: `python -m agentic_redteam.ingest.ingest_catalog`.
2. Diff `agentic_redteam/catalog/data/presets.json`: `plugins` + `recommended_strategies` unchanged
   vs. previous output; `category_index` gone.
3. `pytest tests/ingest tests/catalog tests/engine -q` passes.
4. Wizard spot-check (`web/presenters.py` → step 2): OWASP Agentic still shows its 22 plugins and
   `[jailbreak, jailbreak-templates, jailbreak:composite, crescendo]`.
5. If the optional fix is included: `resolve()` yields a `basic` plan for `system-prompt-override`
   and `agentic:memory-poisoning` under the OWASP Agentic preset.
