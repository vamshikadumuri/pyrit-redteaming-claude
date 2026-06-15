# GCP Hosting Cost Analysis — Dolphin-X1-Llama-3.1-405B

**Purpose:** Cost and infrastructure options for self-hosting the `dphn/Dolphin-X1-Llama-3.1-405B` attacker model on GCP, for use as the in-loop adversarial generator in the PyRIT red-teaming pipeline.

**Source of weights:** On-prem MLflow registry → one-time push to GCP (no runtime internet egress required at serve time).

**Pricing snapshot:** Figures below reflect `us-central1` rates current as of **2026-06-15**. GPU rates fluctuate with availability — re-verify in the [GCP pricing calculator](https://cloud.google.com/products/calculator) before committing budget.

---

## 1. Summary / recommendation

| Question | Answer |
|---|---|
| Cloud Run? | **No.** Hard-capped at 1 GPU/instance (L4 24 GB or RTX PRO 6000 Blackwell 96 GB). 405B needs 200–810 GB. |
| Deployment model | Self-hosted multi-GPU node (GCE VM or Vertex custom endpoint) with vLLM, TP=8. |
| Recommended instance | `a3-highgpu-8g` (8×H100 80 GB) **if** weights are quantized to FP8/INT4; `a3-ultragpu-8g` (8×H200 141 GB) if BF16 is required. |
| Recommended run pattern | **Ephemeral / per-scan** (spin up → run → tear down). 24/7 serving is ~$63–64K/month and unnecessary for red-team workloads. |
| Compliance | Uncensored model → confirm GCE AUP vs. Generative AI Prohibited Use Policy posture with GCP account team / legal before deploy. |

---

## 2. Why Cloud Run is excluded

Cloud Run GPU supports **one GPU per instance**, limited to:

- NVIDIA **L4** — 24 GB VRAM
- NVIDIA **RTX PRO 6000 Blackwell** — 96 GB VRAM

No multi-GPU, no NVLink tensor parallelism. The 405B model's minimum footprint (~205 GB at INT4) exceeds the largest single-GPU Cloud Run option by 2x+, and the BF16 footprint by ~8x. **Cloud Run is not viable for this model at any precision.**

---

## 3. Memory footprint by precision

| Precision | Weights (~405B params) | Fits on 8×H100 (640 GB)? | Fits on 8×H200 (1,128 GB)? |
|---|---|---|---|
| BF16 / FP16 | ~810 GB | ❌ No | ✅ Yes |
| FP8 | ~405 GB | ✅ Yes (+~235 GB KV/overhead) | ✅ Yes (ample) |
| INT4 / AWQ | ~205–230 GB | ✅ Yes (large headroom) | ✅ Yes |

> Weights only; add KV cache + activation overhead on top. Since the weights are owned (from MLflow), quantizing to FP8 or INT4 is the primary lever that drops the requirement from the H200 tier to the cheaper H100 tier.

---

## 4. Instance options

| Instance | GPUs | VRAM (total) | vCPU / RAM | Use when |
|---|---|---|---|---|
| `a3-highgpu-8g` | 8× H100 SXM5 80 GB | 640 GB | 208 / 1,872 GB | FP8 or INT4 quantized weights |
| `a3-ultragpu-8g` | 8× H200 141 GB | 1,128 GB | 224 / 2,952 GB | BF16 full precision |

Serve with vLLM / SGLang / TGI using tensor parallelism `TP=8`, exposed as an OpenAI-compatible endpoint for the PyRIT `OpenAIChatTarget` attacker role.

**Two hosting surfaces:**
1. **GCE VM (direct)** — most control, lowest cost. Run the serving stack yourself on the A3 instance.
2. **Vertex AI custom serving** — managed endpoint via custom container on the same A3 machines. Easier ops, Vertex markup, plus the compliance consideration in §6.

---

## 5. Cost

### Full 8-GPU node, on-demand (us-central1)

| Instance | Per-GPU/hr | Full node/hr | 24×7 month (~730 hr) |
|---|---|---|---|
| `a3-highgpu-8g` (8×H100) | ~$10.98 | ~$87.84 | ~$64,100 |
| `a3-ultragpu-8g` (8×H200) | — | ~$87–98 | ~$63,300 |

### Discount tiers (H100 node, indicative)

| Tier | Approx. discount | Effective node/hr | 24×7 month |
|---|---|---|---|
| On-demand | — | ~$87.84 | ~$64,100 |
| 1-yr CUD | ~20% | ~$70.27 | ~$51,300 |
| 3-yr CUD | ~46% | ~$47.43 | ~$34,600 |
| Spot / preemptible | ~$3.69/GPU/hr | ~$29.52 | ~$21,550 |

### Ephemeral / per-scan economics (recommended)

Red-teaming does **not** require a persistent endpoint. Billing the node only during actual scan hours:

| Scan hours/month | On-demand | Spot |
|---|---|---|
| 20 hr | ~$1,760 | ~$590 |
| 40 hr | ~$3,510 | ~$1,180 |
| 80 hr | ~$7,030 | ~$2,360 |

Spot/preemptible is well-suited to batch attack runs (interruption-tolerant); avoid it for a long-lived serving endpoint. Costs above are compute only — exclude persistent disk, egress, and managed-service (Vertex) charges.

---

## 6. Compliance consideration

This is an **uncensored** model. Key distinction to resolve before deployment:

- **GCE raw compute** is governed by the general **Acceptable Use Policy (AUP)**.
- The **Generative AI Prohibited Use Policy (PUP)** governs Google's *GenAI Services* (e.g., Gemini, managed Vertex GenAI offerings).
- Self-hosting owned weights on rented GPUs is arguably a different posture from consuming a Google GenAI service — but this remains a **gray area**.

The PUP was refreshed Jan 2026, adding exceptions for certain educational/artistic/journalistic/academic use cases, but with **no explicit security-red-teaming carve-out**. The AUP also prohibits using infrastructure to facilitate malware/phishing.

**Action:** Confirm posture with GCP account team / legal before deploy. (Not legal advice.)

---

## 7. Sizing note

405B is unusually heavy for an in-loop attacker model — this is frontier-serving infrastructure for adversarial prompt generation. Before committing to 405B economics, confirm via eval that the larger model materially improves attack success vs. a smaller Dolphin 3.0 variant, which would drop the requirement by ~an order of magnitude in cost.

---

*Generated 2026-06-15. Re-verify all pricing against the GCP pricing calculator before budgeting.*
