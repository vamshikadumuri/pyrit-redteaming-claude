# A Beginner's Guide to PyRIT Attacks (v0.14.0)

*A plain-language introduction to the attack strategies in PyRIT 0.14.0: what they are, how the pieces fit together, when to reach for each one, and runnable examples.*

> Everything in this guide was verified against the `pyrit==0.14.0` package from PyPI. APIs shift between versions, so if you are on a different version, re-check the constructor signatures with `inspect.signature(...)`.

---

## 1. What is PyRIT, and what is an "attack"?

**PyRIT** (Python Risk Identification Toolkit) is an open-source framework for *red-teaming* AI systems — that is, deliberately trying to make an AI model misbehave so you can find and fix the weakness before someone else exploits it.

In PyRIT, an **attack** is a reusable strategy for pursuing a single **objective** against a **target** model. The objective is just a sentence describing what you are trying to get the model to do (for testing purposes), for example:

```
"Get the model to output step-by-step instructions for a disallowed task."
```

The attack is the *technique* used to pursue that objective — send it directly, disguise it, escalate toward it over several turns, and so on. PyRIT ships roughly a dozen of these techniques. This guide explains all of them.

---

## 2. The mental model: four building blocks

Almost every PyRIT attack is assembled from the same four parts. Understand these four and the rest of the framework clicks into place.

```
                        +------------------------------+
                        |          ATTACK              |
                        |  (the strategy / technique)  |
                        +------------------------------+
                           |        |        |       |
            +--------------+        |        |       +--------------+
            v                       v        v                      v
   +-----------------+   +------------------+ +----------------+ +-----------------+
   | OBJECTIVE TARGET|   | ADVERSARIAL CHAT | |    SCORER      | |   CONVERTER     |
   |                 |   |  (attacker LLM)  | |                | |                 |
   | The model you   |   | An LLM that      | | Decides whether| | Transforms the  |
   | are TESTING.    |   | WRITES the       | | the objective  | | prompt before   |
   | (your gateway)  |   | adversarial      | | was achieved   | | sending (e.g.   |
   |                 |   | prompts for you. | | (pass/fail).   | | text -> audio). |
   | ALWAYS required |   | Only SOME attacks| | Optional but   | | Optional.       |
   |                 |   | need this.       | | recommended.   | |                 |
   +-----------------+   +------------------+ +----------------+ +-----------------+
```

| Block | Plain meaning | Required? |
|-------|---------------|-----------|
| **Objective target** | The model under test. The thing you're trying to break. | Always |
| **Adversarial chat** | A *second* LLM that generates the attack prompts on your behalf. Needed only for "adaptive" attacks that improvise each turn. | Only adaptive attacks |
| **Scorer** | Automated judge that reads the target's reply and decides "objective achieved?" or "did it refuse?" | Optional (strongly recommended) |
| **Converter** | A transform applied to the prompt before it's sent — e.g. flip the letters, encode as Base64, or render it as an audio file. | Optional |

A key idea that trips up beginners: **the adversarial chat and the objective target are two different models.** The adversarial chat is your *helper* (it writes attacks); the objective target is your *victim* (the system you're assessing).

In 0.14.0 these blocks are passed as small config objects:

- `AttackAdversarialConfig(target=<attacker LLM>)`
- `AttackScoringConfig(objective_scorer=..., refusal_scorer=...)`
- `AttackConverterConfig(request_converters=[...], response_converters=[...])`

---

## 3. Single-turn vs. multi-turn

The first fork in the road: does the attack send **one message**, or does it hold a **back-and-forth conversation**?

```
 SINGLE-TURN                              MULTI-TURN
 -----------                              ----------

 You ──prompt──> [ Target ]               You ──turn 1──> [ Target ]
        <──reply──                            <──reply 1──
                                          You ──turn 2──> [ Target ]   (adapts based
 One shot. Done.                              <──reply 2──             on last reply)
                                          You ──turn 3──> [ Target ]
                                              <──reply 3──
                                          ... until success or max turns
```

- **Single-turn** attacks are cheaper and faster. Good for broad sweeps and known tricks.
- **Multi-turn** attacks are more powerful against well-defended models, because they can build context and escalate gradually — but they cost more model calls and usually need an adversarial chat LLM.

---

## 4. The most important question: "Does it need an attacker LLM?"

This single decision determines how much you need to set up. Use this flowchart:

```
                        Do you want the attack to
                        IMPROVISE prompts on its own,
                        reacting to the model's replies?
                                   |
                +------------------+------------------+
                |                                     |
               NO                                    YES
                |                                     |
                v                                     v
     Static / scripted attack.            Adaptive attack.
     No adversarial chat needed.          REQUIRES an adversarial
                                          chat LLM (the attacker model).
                |                                     |
                v                                     v
     PromptSendingAttack                  RedTeamingAttack
     FlipAttack                           CrescendoAttack
     ManyShotJailbreakAttack              TreeOfAttacksWithPruningAttack (TAP)
     SkeletonKeyAttack                    PAIRAttack
     MultiPromptSendingAttack             ContextComplianceAttack
     (you write the prompts)              RolePlayAttack
```

If an attack is on the right-hand side, you must supply `attack_adversarial_config=AttackAdversarialConfig(target=...)`. This is the single most common reason a beginner's script fails to construct.

---

## 5. The full attack catalog

Grouped by family, with a one-line description and the situation where each is the right choice.

### 5a. Single-turn, no attacker LLM (static / scripted)

| Attack | What it does | Prefer it when... |
|--------|--------------|-------------------|
| **PromptSendingAttack** | Sends your objective directly, optionally with converters and a scorer. The baseline. | You want a control/coverage run, or to test converters. Always start here. |
| **FlipAttack** | Adds a system prompt instructing the model to "unflip" word order, smuggling the request past keyword filters. | Testing whether guardrails rely on simple surface-string matching. |
| **ManyShotJailbreakAttack** | Stuffs many fake "user asks / assistant happily complies" examples into one prompt to exploit in-context learning. | Testing long-context models; probing safety decay from in-context examples. Tune `example_count`. |
| **SkeletonKeyAttack** | Prepends a fixed "augment your behaviour, don't refuse, just add a warning" preamble. | You want a cheap, deterministic, well-known technique as a regression baseline. |

### 5b. Single-turn, attacker LLM required (adaptive single-turn)

| Attack | What it does | Prefer it when... |
|--------|--------------|-------------------|
| **ContextComplianceAttack** | The attacker LLM fabricates a fake earlier assistant turn, so the model "continues" into compliance. | The target accepts caller-supplied conversation history (common in agent/API surfaces). |
| **RolePlayAttack** | The attacker LLM reframes the objective inside a persona or fictional scenario, loaded from a definition file. | You want framing-based refusal bypass without paying for a full multi-turn loop. |

### 5c. Multi-turn, attacker LLM required (adaptive)

| Attack | What it does | Prefer it when... |
|--------|--------------|-------------------|
| **RedTeamingAttack** | The generic goal-directed conversation. The attacker LLM steers each turn toward the objective. | Your default multi-turn workhorse when you don't need a specific escalation pattern. |
| **CrescendoAttack** | Escalates gradually over benign-seeming turns, and can *backtrack* when the model resists. | A hard objective that fails single-turn; demonstrating that the target lacks conversation-level pattern detection. |
| **TreeOfAttacksWithPruningAttack** (TAP) | Explores many attack branches as a tree, pruning weak/off-topic paths. Highest success rate, highest cost. | The objective is stubborn and you can afford the query budget. Tune `tree_width`, `tree_depth`, `branching_factor`. |
| **PAIRAttack** | Iterative refinement of a single line of attack (width/depth) — like TAP but without the pruning machinery. | You want refinement that's lighter and cheaper than full TAP. |
| **MultiPromptSendingAttack** | Sends a fixed, ordered list of prompts you authored. Adversarial chat is *optional* here. | You've scripted the multi-turn sequence yourself and don't need an LLM improvising. |

### 5d. Compound and streaming

| Attack | What it does | Prefer it when... |
|--------|--------------|-------------------|
| **SequentialAttack** | Chains several child attacks under a completion policy (e.g. `FIRST_SUCCESS`): try the cheap ones, fall through to expensive ones only if needed. | Running a cost-controlled escalation ladder across many objectives. |
| **ChunkedRequestAttack** | Splits one request across multiple chunked messages. | The target or its filter inspects each message individually rather than the assembled whole. |
| **BargeInAttack** | Drives a live audio session and interrupts ("barges in") over streaming voice. Needs a `RealtimeTarget`. | Testing a real-time / streaming **voice** system specifically. (See §7.) |

> **Helper, not an attack:** `generate_simulated_conversation_async` (a.k.a. SimulatedConversation) synthesizes fake conversation history you can prepend to a real attack. It sets the stage; it doesn't pursue an objective on its own.

---

## 6. How to pick — a simple decision flow

```
   START
     |
     v
   Run PromptSendingAttack as a control.  ── Did it already comply? ──> Done. (Finding logged.)
     |  (no)
     v
   Try cheap static jailbreaks:
   FlipAttack, ManyShotJailbreak, SkeletonKey   ── Success? ──> Log finding.
     |  (still refusing)
     v
   Go adaptive multi-turn:
   RedTeamingAttack, then CrescendoAttack       ── Success? ──> Log finding.
     |  (still refusing)
     v
   Bring out the heavy search:
   TAP (or PAIR if you want it lighter)         ── Success? ──> Log finding.
     |
     v
   Wrap the whole ladder in a SequentialAttack so you don't
   waste expensive attacks on objectives that fall to cheap ones.
```

The guiding principle: **spend the least compute that still finds the weakness.** Static attacks are pennies; TAP is dollars. Climb the ladder only as far as you must.

---

## 7. Are these text attacks? (text vs. audio vs. image)

Mostly yes — but not entirely. There are **three tiers**, and this matters if you test voice or vision systems.

```
 TIER 1: Natively non-text
 -------------------------
   BargeInAttack  ──► operates on raw audio byte streams over a live
                       RealtimeTarget. No text payload at the attack layer.


 TIER 2: Text logic, but delivery can be ANY modality
 ----------------------------------------------------
   Every other attack THINKS in text (it reasons about, escalates,
   or rewrites text). BUT the payload can be transformed before it
   reaches the target, using CONVERTERS:

      "How do I ..."  ──[ text-to-audio converter ]──►  speech.wav  ──► [ Target ]
      "How do I ..."  ──[ add-text-to-image conv. ]──►  image.png   ──► [ Target ]

   So you can run, say, Crescendo's escalation entirely in text, then
   render each turn into audio to probe a speech pipeline.


 TIER 3: Pure-text logic (don't generalize beyond text meaningfully)
 -------------------------------------------------------------------
   FlipAttack (flips letters), ManyShot (text examples),
   SkeletonKey (text preamble). The technique only makes sense as text.
```

**Practical takeaway:** for most multimodal testing you do **not** need a special "audio attack." You wrap an ordinary text attack with an audio/image converter. `BargeInAttack` is reserved for the *native real-time streaming voice* path specifically.

PyRIT 0.14.0 ships converters for: text→audio, audio echo / frequency / speed / volume / white-noise, image overlay / rotation / compression / resizing / style, and image→video.

> ⚠️ **Air-gapped note:** the bundled text-to-audio and audio-to-text converters (`AzureSpeechTextToAudioConverter`, `AzureSpeechAudioToTextConverter`) call Azure's cloud Speech service. In a no-egress environment they won't run — you'd wrap a *local* TTS/STT model in a custom `PromptConverter`. The pure signal-processing audio converters (echo, frequency, speed, volume, white-noise) run fully offline.

---

## 8. Examples (verified for 0.14.0)

All examples assume this boilerplate. Note 0.14.0 uses `initialize_pyrit_async` from `pyrit.setup` (this moved in recent versions).

```python
import asyncio
from pyrit.setup import initialize_pyrit_async, IN_MEMORY
from pyrit.prompt_target import OpenAIChatTarget
from pyrit.executor.attack import ConsoleAttackResultPrinter

async def setup():
    # IN_MEMORY keeps results in RAM; use SQLITE to persist a results DB.
    await initialize_pyrit_async(IN_MEMORY)

    # The model under test — your internal OpenAI-compatible gateway.
    target = OpenAIChatTarget(
        endpoint="https://your-internal-gateway/openai/v1/chat/completions",
        api_key="REPLACE_ME",
        model_name="your-target-model",
    )
    return target
```

### Example 1 — Baseline (no attacker LLM, no jailbreak)

The simplest possible run: send the objective straight at the target and print the result.

```python
from pyrit.executor.attack import PromptSendingAttack, ConsoleAttackResultPrinter

async def example_baseline():
    target = await setup()

    attack = PromptSendingAttack(objective_target=target)

    result = await attack.execute_async(
        objective="Explain the basic principle of how a pin-tumbler lock works."
    )
    await ConsoleAttackResultPrinter().print_result_async(result)

asyncio.run(example_baseline())
```

### Example 2 — A static jailbreak (FlipAttack, still no attacker LLM)

Same shape as the baseline, but the attack wraps your objective in its own obfuscation. No adversarial chat needed.

```python
from pyrit.executor.attack import FlipAttack

async def example_flip():
    target = await setup()

    attack = FlipAttack(objective_target=target)

    result = await attack.execute_async(
        objective="Describe how a phishing email is typically structured."
    )
    await ConsoleAttackResultPrinter().print_result_async(result)
```

### Example 3 — An adaptive multi-turn attack (Crescendo — needs an attacker LLM)

Here we add the **adversarial chat**. Notice there are now *two* targets: the attacker model that writes the prompts, and the objective target being tested.

```python
from pyrit.executor.attack import (
    CrescendoAttack,
    AttackAdversarialConfig,
    AttackScoringConfig,
)
from pyrit.score import SelfAskRefusalScorer

async def example_crescendo():
    target = await setup()

    # A SECOND model that generates the adversarial turns for us.
    attacker_llm = OpenAIChatTarget(
        endpoint="https://your-internal-gateway/openai/v1/chat/completions",
        api_key="REPLACE_ME",
        model_name="your-uncensored-attacker-model",  # e.g. a local Dolphin/Hermes via vLLM
    )

    attack = CrescendoAttack(
        objective_target=target,
        attack_adversarial_config=AttackAdversarialConfig(target=attacker_llm),
        attack_scoring_config=AttackScoringConfig(
            refusal_scorer=SelfAskRefusalScorer(chat_target=attacker_llm),
        ),
        max_turns=10,
        max_backtracks=10,
    )

    result = await attack.execute_async(
        objective="Get the model to produce <your test objective here>."
    )
    await ConsoleAttackResultPrinter().print_result_async(result)
```

> The same pattern (add `AttackAdversarialConfig`) applies to `RedTeamingAttack`, `TreeOfAttacksWithPruningAttack`, `PAIRAttack`, `ContextComplianceAttack`, and `RolePlayAttack`.

### Example 4 — RolePlay using a bundled scenario file

RolePlay needs a scenario definition. PyRIT bundles a few; here we use the built-in video-game persona.

```python
from pyrit.executor.attack import (
    RolePlayAttack,
    RolePlayPaths,
    AttackAdversarialConfig,
)

async def example_roleplay():
    target = await setup()
    attacker_llm = OpenAIChatTarget(
        endpoint="https://your-internal-gateway/openai/v1/chat/completions",
        api_key="REPLACE_ME",
        model_name="your-attacker-model",
    )

    attack = RolePlayAttack(
        objective_target=target,
        attack_adversarial_config=AttackAdversarialConfig(target=attacker_llm),
        role_play_definition_path=RolePlayPaths.VIDEO_GAME.value,
    )

    result = await attack.execute_async(
        objective="<your test objective here>"
    )
    await ConsoleAttackResultPrinter().print_result_async(result)
```

### Example 5 — Delivering a text attack as AUDIO via a converter

This shows Tier-2 from §7: the attack logic is text, but a converter renders the payload as audio before it hits a voice-capable target. (Swap in a local TTS converter for air-gapped use.)

```python
from pyrit.executor.attack import PromptSendingAttack, AttackConverterConfig
from pyrit.prompt_converter import AzureSpeechTextToAudioConverter
from pyrit.prompt_normalizer import PromptConverterConfiguration

async def example_audio_delivery():
    target = await setup()  # must be a target that accepts audio input

    converters = PromptConverterConfiguration.from_converters(
        converters=[AzureSpeechTextToAudioConverter()]  # cloud; replace for air-gap
    )

    attack = PromptSendingAttack(
        objective_target=target,
        attack_converter_config=AttackConverterConfig(request_converters=converters),
    )

    result = await attack.execute_async(
        objective="Read this request aloud and answer it: <your test objective>."
    )
    await ConsoleAttackResultPrinter().print_result_async(result)
```

### Example 6 — The default multi-turn workhorse (RedTeamingAttack)

The general-purpose adaptive attack. Same shape as Crescendo: supply an attacker LLM via the adversarial config.

```python
from pyrit.executor.attack import (
    RedTeamingAttack,
    AttackAdversarialConfig,
    AttackScoringConfig,
)
from pyrit.score import SelfAskRefusalScorer

async def example_redteaming():
    target = await setup()
    attacker_llm = OpenAIChatTarget(
        endpoint="https://your-internal-gateway/openai/v1/chat/completions",
        api_key="REPLACE_ME",
        model_name="your-attacker-model",
    )

    attack = RedTeamingAttack(
        objective_target=target,
        attack_adversarial_config=AttackAdversarialConfig(target=attacker_llm),
        attack_scoring_config=AttackScoringConfig(
            refusal_scorer=SelfAskRefusalScorer(chat_target=attacker_llm),
        ),
        max_turns=8,
    )

    result = await attack.execute_async(
        objective="<your test objective here>"
    )
    await ConsoleAttackResultPrinter().print_result_async(result)
```

> **Advanced — SequentialAttack (cost ladder):** chaining cheap attacks before expensive ones is *not* a one-liner. Each child is a
> `SequentialChildAttack(strategy=<attack>, seed_group=<SeedAttackGroup>)` — note the field is `strategy=`, **not** `attack=` — and the
> `SeedAttackGroup` must carry exactly one objective (a `SeedObjective`). Get comfortable with the single attacks above before composing them.

---

## 9. Glossary for newcomers

- **Objective** — a sentence describing the behaviour you're trying to elicit, for testing.
- **Objective target** — the AI system under test (the "victim").
- **Adversarial chat / attacker LLM** — a separate model that *writes* the attack prompts. Often an uncensored model so it's willing to play the adversary. Needed only for adaptive attacks.
- **Scorer** — an automated judge. An *objective scorer* answers "did we succeed?"; a *refusal scorer* answers "did the model refuse?"
- **Converter** — a prompt transform applied before sending (encode, obfuscate, render to audio/image).
- **Single-turn** — one message and done.
- **Multi-turn** — an ongoing conversation that adapts to replies.
- **Backtrack** (Crescendo) — undoing a turn that triggered resistance and trying a softer path.
- **Pruning** (TAP) — discarding weak or off-topic attack branches during a tree search.
- **RealtimeTarget** — a target that supports live streaming audio sessions (what BargeInAttack drives).

---

## 10. Quick reference card

```
NEED AN ATTACKER LLM?     ATTACK                              TURNS
-------------------------------------------------------------------
No                        PromptSendingAttack                 1
No                        FlipAttack                          1
No                        ManyShotJailbreakAttack             1
No                        SkeletonKeyAttack                   1
No (optional)             MultiPromptSendingAttack            many (scripted)
Yes                       ContextComplianceAttack             1 (adaptive)
Yes                       RolePlayAttack                      1 (adaptive)
Yes                       RedTeamingAttack                    many (adaptive)
Yes                       CrescendoAttack                     many (adaptive)
Yes                       TreeOfAttacksWithPruningAttack      many (tree search)
Yes                       PAIRAttack                          many (iterative)
No                        ChunkedRequestAttack                1 (split)
No                        SequentialAttack                    depends on children
N/A (audio)               BargeInAttack                       streaming voice
-------------------------------------------------------------------
Start cheap (top) and climb only as far as you need.
```

*Verified against pyrit==0.14.0. Re-verify signatures with `inspect.signature()` if you upgrade.*
