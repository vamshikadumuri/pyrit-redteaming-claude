# Promptfoo Plugin Catalog — How It's Sourced & Generated

*A beginner's guide to `promptfoo_plugins_catalog_1.xlsx`*
*Last updated: 2026-06-14*

---

## 1. What is this file, in one sentence?

It's a **lookup table of 157 red-team "attack categories"** (called *plugins*) borrowed
from the open-source tool **promptfoo**, re-packaged so our own **PyRIT**-based,
air-gapped red-teaming system can use them to generate and grade attacks against an LLM.

Think of it as a **menu of things that can go wrong with an AI**, where each menu item
comes with: what it tests, a one-line "attacker goal," and the checklist a grader uses to
decide whether the AI failed.

---

## 2. The 30-second mental model

Our red-teaming pipeline has three roles, all pointed at our internal GCP gateway:

```
  ┌─────────────┐      attack prompts       ┌─────────────┐     answer      ┌─────────────┐
  │  ATTACKER   │ ────────────────────────▶ │   TARGET    │ ──────────────▶ │   JUDGE     │
  │ (local LLM, │                           │ (the model  │                 │ (scorer +   │
  │  Dolphin)   │ ◀──────────────────────── │  under test)│                 │  rubric)    │
  └─────────────┘     adapts next turn       └─────────────┘                 └─────────────┘
        ▲                                                                           ▲
        │  needs a GOAL to pursue                                                   │  needs a RUBRIC to grade against
        │                                                                           │
        └───────────────────────────  THIS CATALOG  ─────────────────────────────-─┘
```

- The **attacker** needs a *goal* to pursue → that's the **Imperative Seed** column.
- The **judge** needs a *checklist* to grade against → that's the **Grading Rubric** column.

Promptfoo does all three roles on its own servers using private templates we can't see.
We can't call those servers (air-gap), so we **extracted the parts promptfoo publishes
under its MIT open-source license** and drive them with our *own* local attacker and judge.
This catalog is that extracted material.

---

## 3. Where does the data actually come from?

Everything is pulled from the **promptfoo GitHub source code** (MIT-licensed), version
**`0.121.13`**, re-verified against the current latest **`0.121.15`** on 2026-06-14.
Two source files matter most:

| What | Source file in promptfoo | Becomes which column |
|---|---|---|
| Plugin descriptions | `src/redteam/constants/metadata.ts` → `pluginDescriptions` map | **Objective (description)** |
| Coding-agent descriptions | `src/redteam/constants/codingAgents.ts` | (same column, for `coding-agent:*`) |
| Grading prompts | `src/redteam/plugins/**/*.ts` (the `Grader` classes) | **Grading Rubric / Notes** |
| Framework tags, severity, strategies | `metadata.ts`, `frameworks.ts`, `strategies.ts` | the OWASP/MITRE/Severity columns, Presets & Strategy Map sheets |

### Two things a beginner should know about the source

**(a) There are TWO description maps in promptfoo, and we picked the better one.**
- `subCategoryDescriptions` = short UI labels (e.g. *"Age-related bias detection"*).
- `pluginDescriptions` = richer one-liners (e.g. *"Tests handling of age-related stereotypes…"*).
We use `pluginDescriptions`. If you ever re-extract, **keep pulling from `pluginDescriptions`,
not the short one.**

**(b) There are TWO ways promptfoo grades, and they look different in the cells.**
1. **Static LLM rubric** — the grader class has a written prompt (e.g. `BflaGrader`). These
   use placeholders like `{{purpose}}`, `{{prompt}}`, `{{output}}` that get filled in at run time.
2. **Runtime-rendered rubric** — the grader builds its prompt in code (e.g. the whole
   `financial:*` family). In raw source these used `${vars.purpose}` (a JavaScript style).
   **We converted those to `{{purpose}}`** so they behave like the others (see §5).

Some plugins have **no static rubric at all** — they're graded by running code (counting a
leaked "canary" string, detecting a refusal, etc.). Those cells say `[Dynamic …]` or
`[No static LLM rubric …]`.

> **Is the import trustworthy?** Yes. Every description matches the latest source exactly
> (157/157), and every static rubric that maps to a source grader matches exactly (53/53).
> Nothing here is paraphrased or made up — it's transcribed from promptfoo's code.

---

## 4. Column-by-column guide (Plugins sheet)

| Column | Plain-English meaning |
|---|---|
| **Plugin ID** | The code name, e.g. `bola`. Full promptfoo id is `promptfoo:redteam:bola`. |
| **Name** | Human-readable title. |
| **Severity** | promptfoo's default severity (you can override it). |
| **Plugin Type** | `Generative` = the attacker must *make up* test prompts. `Dataset` = prompts come from a ready-made file. `Config-required` = you supply your own. |
| **OWASP LLM / Agentic / API** | Which industry framework category this maps to (blank = not mapped). |
| **MITRE ATLAS** | Which ATLAS attack-stage it maps to. |
| **Objective Source** | *Where real attack prompts come from*: a dataset, your own config, or local generation. |
| **Objective (description)** | *What the plugin tests*, in promptfoo's words. This is the high-level intent. |
| **Imperative Seed / Attacker-Goal Hint** | *The goal we hand the attacker LLM* — "Get the target to do X." This is the description rewritten as an order. |
| **Grading Rubric / Notes** | *The checklist the judge uses* to decide pass/fail. |
| **Grader Mechanism (verified)** ⟵ *new* | *How* this plugin is graded: LLM rubric / Dynamic / Programmatic / Dataset / Config-required. |
| **PyRIT Scoring Note** ⟵ *new* | *How to wire it into PyRIT*, including the polarity flip (see §5). |

**Objective vs. Seed — what's the difference?** The *Objective* is a description
("Tests whether the agent leaks secrets"). The *Seed* is a command aimed at the attacker
("Get the agent to leak secrets"). The attacker LLM expands the seed into many concrete
attack prompts.

---

## 5. The two gotchas every beginner hits

### Gotcha #1 — "Pass" means the OPPOSITE thing in promptfoo vs. PyRIT

- In **promptfoo**, a rubric scores **`pass = 1 = the AI was SAFE`** (good behaviour passes).
- In **PyRIT**, an objective scorer expects **`true = the attack SUCCEEDED = a VIOLATION`**.

These are backwards from each other. If you wire a promptfoo rubric straight into a PyRIT
scorer, every result is inverted. **Fix:** wrap the scorer with PyRIT's
`TrueFalseInverterScorer`. The new **PyRIT Scoring Note** column reminds you of this per row.

### Gotcha #2 — Placeholder syntax

Promptfoo rubrics contain blanks that get filled at run time. Two styles existed in source:
- `{{purpose}}` `{{prompt}}` `{{output}}` (Jinja/Nunjucks — PyRIT understands this)
- `${vars.purpose}` (JavaScript — PyRIT does **not** understand this; it would print literally)

**We converted all `${vars.X}` to `{{X}}`** in this workbook so every rubric renders the
same way in PyRIT. (44 cells were converted; grading meaning unchanged.)

---

## 6. The three grading families (and how to score each in PyRIT)

| Family | Cell looks like | How to grade in PyRIT |
|---|---|---|
| **LLM rubric** (most plugins) | A written FAIL/PASS prompt with `{{…}}` blanks | `SelfAskTrueFalseScorer` / `SelfAskScaleScorer` + **`TrueFalseInverterScorer`** |
| **Dynamic** (all `coding-agent:*`, memory-poisoning) | `[Dynamic — runtime-composed…]` | Judge the multi-step trace; `InsecureCodeScorer` + canary/`SubStringScorer`. No inverter. |
| **Programmatic** (e.g. `cross-session-leak`) | `[No static LLM rubric…]` | Heuristic: `SubStringScorer`, canary match, or refusal detection. No inverter. |
| **Dataset** (e.g. `beavertails`) | "Dataset content-safety evaluator" | Use the dataset's own labels/moderation. Objectives = the dataset rows. |

> For **Dynamic** plugins there's no static rubric to copy, so the **Seed itself carries the
> success goal** — that's why the coding-agent seeds were rewritten to be self-contained.

---

## 7. What changed in the 2026-06-14 enrichment pass

Nothing about the *source data* was "corrected" — it was already faithful. What we improved
was **usability for our PyRIT pipeline**:

1. **Re-verified** all 157 objectives against the latest promptfoo (`0.121.15`) — exact match.
2. **Fixed 37 attacker-goal Seeds** that were mechanically generated and flawed:
   - **7 were backwards** (aimed the attacker at the *safe* behaviour — the most serious bug).
   - **7 were grammatically broken** ("perform or enable plants CI…").
   - **7 had broken capitalization** ("fair Housing Act", "family Educational Rights").
   - **8 were vague** ("…: memory poisoning attacks.") and got concrete goals.
   - The **coding-agent** seeds were made self-contained (their graders are dynamic).
3. **Normalized 44 rubrics** from `${vars.X}` to `{{X}}` so they render in PyRIT.
4. **Added two columns**: *Grader Mechanism* and *PyRIT Scoring Note*.
5. **Added an "Enrichment Log" sheet** listing every single change with a reason (audit trail).

The other ~115 seeds and all rubric *content* were left untouched because they were
already sound.

---

## 8. How to refresh this catalog from a newer promptfoo

When promptfoo releases a new version and you want to update:

1. Download the source for the new tag, e.g.
   `https://codeload.github.com/promptfoo/promptfoo/tar.gz/refs/tags/<version>`
2. Re-extract **objectives** from `src/redteam/constants/metadata.ts` → `pluginDescriptions`
   (plus `codingAgents.ts`).
3. Re-extract **rubrics** from the `Grader` classes in `src/redteam/plugins/**` — remember
   some use a written `rubric = …` and some use `renderRubric() { … }`.
4. **Re-apply the two normalizations**: convert `${vars.X}` → `{{X}}`, and remember the
   `pass=safe → true=violation` polarity flip when scoring.
5. **Re-check the Seeds** for the two failure patterns: *backwards polarity* (when the
   description says "tests whether the system does the GOOD thing") and *broken grammar*.
6. Diff against this version to see what plugins were added or changed.

---

## 9. Mini-glossary

- **Plugin** — one attack category (e.g. "broken object-level authorization").
- **Objective** — what the plugin tests (a description).
- **Seed / Attacker-Goal Hint** — the goal we hand the attacker LLM to pursue.
- **Rubric** — the checklist the judge uses to decide if the AI failed.
- **Attacker LLM** — our local uncensored model (Dolphin) that writes the attack prompts.
- **Target** — the model being tested (our internal gateway).
- **Judge / Scorer** — decides pass/fail; in PyRIT, `true` = the attack succeeded.
- **Polarity** — which direction "pass/true" points. promptfoo and PyRIT are opposite.
- **Air-gap** — no internet at run time; everything must run from local copies.
- **PyRIT** — Microsoft's open-source red-teaming framework we build on (v0.13.0).
- **promptfoo** — the open-source tool whose taxonomy we borrowed (MIT license).
- **Dynamic rubric** — grading prompt built in code at run time, not a fixed string.
- **Canary** — a secret marker string; if it shows up in the output, data leaked.

---

*This catalog reuses promptfoo's plugin taxonomy under its MIT license. The objective and
rubric text is transcribed from promptfoo source; the Seed column and the two PyRIT columns
are our own additions for the air-gapped PyRIT pipeline.*
