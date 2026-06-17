# Choosing the "Attacker" AI Model

## In one sentence

We need to pick an open-weight AI model that **writes test attack prompts** to probe our own AI app for weaknesses, and this document explains which model we chose and why.

---

## Quick background

- **Red-teaming** = safely attacking our own system first, to find weaknesses before real attackers do.
- **Attacker model (a.k.a. generator)** = the AI that *writes* the test prompts we throw at our app.
- **promptfoo** = an open-source testing tool. Its **plugins** are categories of weakness to test for (e.g. leaking private data, prompt injection, harmful output).
- **PyRIT** = Microsoft's red-teaming toolkit. Its **strategies** are ways to *deliver or escalate* an attack (e.g. disguising it, encoding it, building up over multiple messages).
- **Refusal** = when an AI declines to answer. A normal safety model refuses a lot; for *writing test prompts* that gets in the way, so we need a model that won't constantly refuse.

**How our setup works:** We give the model a short description of the plugin (what weakness to probe) plus what our app does, and ask it to write a clean test prompt. PyRIT then takes that prompt and applies the attack strategy. So the model only needs to write a good starting prompt — the toolkit does the rest.

---

## What we actually need from the model

Because we tell the model what to do through instructions each time (we are **not** retraining it), the single most important quality is that it **follows detailed instructions well**. The other needs, in order:

1. **Follows instructions reliably** — does what the plugin description and app purpose ask.
2. **Rarely refuses** — and refuses *consistently little* across all weakness categories, so we don't get blind spots.
3. **Produces variety** — different wordings and angles, so we cover more ground.
4. **Fast and affordable to run** — we generate many prompts.
5. **Runs locally** — keeps our app details and test data off outside services.

---

## Two ways models get "uncensored" (why this matters)

There are two common methods, and they behave differently:

- **Retrained to comply (SFT / "uncensored" fine-tunes):** the model is taught, during normal training, not to refuse. It keeps its skills — including following instructions — intact. **This is what we prefer.**
- **Abliteration:** a quick surgical tweak to the model's internals that removes the "refuse" reflex. It's cheap and keeps the model's creativity, **but** it can (a) make the model worse at following instructions and (b) occasionally start refusing again in spots. A "**healed**" abliterated model has a light repair pass afterward and is much safer to use. *Newer abliteration methods (e.g. "Heretic", "HauhauCS") are designed to remove refusals with less damage in the first place, reducing the need for a separate healing step — but quality still varies by method, so it must be tested.*

**Our rule of thumb:** prefer instruction-following + steerable models; if we use an abliterated one, use a **healed** version (or one made with a modern low-damage method), never a raw one.

> Note: Hermes 4 is **not** abliterated — it is a retrained, steerable model. That is exactly why it is our first choice.

---

## Recommended models, ranked for this use case

Start at #1. Add the others as supporting roles in a rotation.

> **Currency caveat (read first):** This space changes almost weekly, and there is **no authoritative benchmark for this exact job** (red-team prompt generation). The public "best uncensored model" lists are mostly SEO articles or aimed at creative writing/roleplay, not security testing. Treat the picks below as **strong starting candidates as of mid-2026**, not a final verdict — re-check for newer builds at deploy time and **test 2–3 candidates on your own plugin specs** (measure refusal rate + how well each obeys the spec) before standardizing.

| Rank | Model | Best for | HuggingFace link |
|---|---|---|---|
| **1** | **Hermes 4 — Llama 3.1 70B** | **Main workhorse.** Retrained and steerable: you control it with instructions, it follows them well, and it rarely refuses. Newer generation than Hermes 3, stronger at format-faithful output. Has an optional reasoning mode — turn it **off** for cheap bulk generation. | https://huggingface.co/NousResearch/Hermes-4-70B  (FP8: `…-70B-FP8`; GGUF: https://huggingface.co/bartowski/NousResearch_Hermes-4-70B-GGUF) |
| **2** | **Dolphin 3.0 (Llama 3.1 8B, or Mistral 24B)** | **High-volume, low-cost.** Lightweight, uncensored, good at following technical prompts — ideal for generating many test prompts cheaply. | https://huggingface.co/dphn/Dolphin3.0-Llama3.1-8B  •  Mistral variant (SFT, not abliterated): https://huggingface.co/dphn/Dolphin3.0-Mistral-24B |
| **3** | **Dolphin 3.0 R1 — Mistral 24B** | **Hard, app-specific probes.** A fine-tuned (SFT) uncensored model with built-in step-by-step *reasoning* — best when a test prompt must be tailored closely to what our app does. Fine-tuned, **not** abliterated, so it stays consistent with the rest of the list. *Higher-ceiling alternative to test: `puwaer/Qwen3-Next-80B-A3B-Thinking-GRPO-Uncensored` — a current-gen, SFT+GRPO (not abliterated) reasoner on a stronger base, but an individual LoRA build with less-proven quality.* | https://huggingface.co/dphn/Dolphin3.0-R1-Mistral-24B |
| **4** | **Dolphin X1 — Llama 3.1 405B** | **Heavyweight backup.** Most capable, for niche cases where smaller models produce generic prompts. Expensive to run, so use sparingly. (A Qwen3-235B-based Dolphin X1 is on their roadmap — worth watching.) | https://huggingface.co/dphn/Dolphin-X1-Llama-3.1-405B |

**Simple plan:** run **#1 (Hermes 4 70B)** as the default, keep **#2 (Dolphin 3.0)** for cheap bulk generation, and pull in **#3–#4** when you need tougher or more specialized prompts.

> These four cover the axes that matter — base families (Llama, Mistral), sizes from 8B to 405B, and both plain and reasoning-capable models — while staying consistent on method: **all four are fine-tuned (SFT), none abliterated.**

> Model versions on HuggingFace change often. Check for a newer version of each before deploying, and test it on our own prompts first.
>


---

## How each model was made (training method)

This explains *why* each model rarely refuses — and it's the main reason we ranked them the way we did. Recall the two approaches:

- **Retrained to comply (fine-tuned):** the model is *taught* during normal training not to refuse. It keeps its skills and follows instructions well. **(Preferred.)**
- **Abliterated:** a surgical edit removes the "refuse" reflex *after* training. Cheap, keeps creativity, but can weaken instruction-following and refuse again in spots. A **"healed"** version adds a light repair pass afterward.

| # | Model | Built on (base model) | How it was made | "Refuse" reflex removed by |
|---|---|---|---|---|
| 1 | **Hermes 4 — Llama 3.1 70B** | Meta Llama 3.1 70B | **Retrained (fine-tuned)** by NousResearch on a large new post-training corpus (verified reasoning traces + instruction data); deliberately "neutrally aligned" and steered by the system prompt. Hybrid reasoning mode. **Not abliterated.** | Training choices (built to be steerable + low-refusal) |
| 2 | **Dolphin 3.0 (Llama 3.1 8B / Mistral 24B)** | Llama 3.1 8B  /  Mistral-Small-24B | **Retrained (fine-tuned, SFT)** on the Dolphin instruction dataset; non-refusal comes from the training data. Steered by the system prompt. **Not abliterated.** | Training data (uncensored instruction mix) |
| 3 | **Dolphin 3.0 R1 — Mistral 24B** | Mistral-Small-24B | **Retrained (fine-tuned, SFT)** by dphn, with DeepSeek-R1-style reasoning traces added in training. Uncensored via training data. Steered by the system prompt. **Not abliterated.** | Training data (uncensored instruction + reasoning mix) |
| 4 | **Dolphin X1 — Llama 3.1 405B** | AllenAI Llama-3.1-Tulu-3-405B (itself SFT + DPO + RLVR) | **Retrained (fine-tuned)** by dphn to be uncensored / de-aligned. Steered by the system prompt. **Not abliterated.** | Training choices (fine-tuned to be uncensored) |

**Plain takeaway:** all four picks are **retrained-to-comply (fine-tuned)** models — none are abliterated. They keep their skills and follow instructions, which is exactly what this use case needs most. #3 adds step-by-step reasoning for harder, app-specific probes without breaking that consistency.

> Note on the two Dolphin Mistral builds: `Dolphin3.0-Mistral-24B` (slot #2) is the plain SFT version for cheap generation; `Dolphin3.0-R1-Mistral-24B` (slot #3) is the same SFT model with reasoning traces added — use it when you want step-by-step tailoring. Both are fine-tuned, neither is abliterated. (Avoid the `huihui-ai/...-abliterated` repackage of these unless you specifically want an abliterated build.)

---

## How to get good, varied results

- **Keep the two jobs separate.** Let the model write a clean starting prompt; let PyRIT apply the attack strategy. Don't ask the model to do both at once — quality drops.
- **Always include what the app does.** Tell the model to tailor each test to our specific app, not write generic prompts.
- **Turn up variety.** Use a higher "temperature" setting and give 2–3 short example styles per plugin, so prompts don't come out near-identical.
- **Use more than one model.** A main model plus a variety model widens coverage.

---

## Known limitation

When everything is driven by instructions (no retraining), results on **unusual or brand-new weakness categories** may come out generic — limited by what the model already knows. That's an accepted trade-off for not having to build a training dataset. The large #4 model (Dolphin X1 405B) is the fallback for those tougher cases.

---

## Responsible-use note

This is for **authorized testing of systems we own or are permitted to test**. All generated prompts and app details stay on our own local infrastructure.
