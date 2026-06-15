# GCP Hosting Cost Analysis — Dolphin-X1-Llama-3.1-405B

**Purpose:** Cost and infrastructure options for self-hosting the `dphn/Dolphin-X1-Llama-3.1-405B` attacker model on GCP, for use as the in-loop adversarial generator in the PyRIT red-teaming pipeline.

**Source of weights:** On-prem MLflow registry → one-time push to GCP (no runtime internet egress required at serve time).

**Pricing provenance:** All dollar figures below are taken from Google's official [Accelerator-optimized VM pricing](https://cloud.google.com/products/compute/pricing/accelerator-optimized) price sheet, region `us-central1`, retrieved **2026-06-15**. GPU rates change; re-verify in the [pricing calculator](https://cloud.google.com/products/calculator) before committing budget.

---

## 1. Summary / recommendation

| Question | Answer |
|---|---|
| Cloud Run? | **No.** Hard-capped at 1 GPU/instance (L4 24 GB or RTX PRO 6000 Blackwell 96 GB). 405B needs 200–810 GB. |
| Deployment model | Self-hosted multi-GPU node (GCE VM or Vertex custom endpoint) with vLLM, TP=8. |
| Recommended instance | **`a3-ultragpu-8g` (8×H200, 1,128 GB)** — cheaper on-demand than the H100 node *and* more memory; runs BF16 or quantized. Drop to `a3-highgpu-8g` (8×H100, 640 GB) only for the cheaper spot rate, which forces FP8/INT4. |
| Cheapest (quantized) | `g4-standard-384` (8×RTX PRO 6000, 768 GB) at $36/hr — **but PCIe-only, no NVLink**; validate TP=8 throughput first. |
| Cheapest (BF16) | `a4-highgpu-8g` (8×B200, 1,440 GB) via DWS spot ($34.24/hr) or flex-start ($64.44/hr). |
| Recommended run pattern | **Ephemeral / per-scan** (spin up → run → tear down) or DWS flex-start. 24/7 serving is ~$62–65K/month and unnecessary for red-team workloads. |
| Compliance | Uncensored model → confirm GCE AUP vs. Generative AI Prohibited Use Policy posture with GCP account team / legal before deploy. |

---

## 2. Why Cloud Run is excluded

Cloud Run GPU supports **one GPU per instance**, limited to:

- NVIDIA **L4** — 24 GB VRAM
- NVIDIA **RTX PRO 6000 Blackwell** — 96 GB VRAM

No multi-GPU, no NVLink tensor parallelism. The 405B model's minimum footprint (~205 GB at INT4) exceeds the largest single-GPU Cloud Run option by 2x+, and the BF16 footprint by ~8x. **Cloud Run is not viable for this model at any precision.**

---

## 3. Memory footprint by precision

| Precision | Weights (~405B params) | Fits 8×H100 (640 GB)? | Fits 8×RTX PRO 6000 (768 GB)? | Fits 8×H200 (1,128 GB)? | Fits 8×B200 (1,440 GB)? |
|---|---|---|---|---|---|
| BF16 / FP16 | ~810 GB | ❌ | ❌ | ✅ | ✅ |
| FP8 | ~405 GB | ✅ | ✅ | ✅ | ✅ |
| INT4 / AWQ | ~205–230 GB | ✅ | ✅ | ✅ | ✅ |

> Weights only; add KV cache + activation overhead on top. Quantizing owned weights (FP8/INT4) is the main lever to fit cheaper tiers.

---

## 4. Instance options

| Instance | GPUs | VRAM (total) | vCPU / host RAM | Interconnect | Use when |
|---|---|---|---|---|---|
| `g4-standard-384` | 8× RTX PRO 6000 96 GB | 768 GB | 384 / 1,440 GB | **PCIe (no NVLink)** | Cheapest; FP8/INT4 only; throughput-validate |
| `a3-highgpu-8g` | 8× H100 SXM5 80 GB | 640 GB | 208 / 1,871 GB | NVLink | FP8/INT4; best spot rate |
| `a3-ultragpu-8g` | 8× H200 141 GB | 1,128 GB | 224 / 2,952 GB | NVLink | **Default** — BF16 or quantized |
| `a4-highgpu-8g` | 8× B200 | 1,440 GB | 224 / 3,968 GB | NVLink | BF16; DWS/spot only (no on-demand listing) |

Serve with vLLM / SGLang / TGI using tensor parallelism `TP=8`, exposed as an OpenAI-compatible endpoint for the PyRIT `OpenAIChatTarget` attacker role.

**Two hosting surfaces:**
1. **GCE VM (direct)** — most control, lowest cost. Run the serving stack yourself on the instance.
2. **Vertex AI custom serving** — managed endpoint via custom container on the same machines. Easier ops, Vertex markup, plus the compliance consideration in §6.

---

## 5. Cost (Google price sheet, us-central1, full node)

### Hourly, all pricing modes

| Instance | On-demand/hr | Spot/hr | 1-yr CUD/hr | 3-yr CUD/hr | DWS flex-start/hr |
|---|---|---|---|---|---|
| `g4-standard-384` (8×RTX PRO 6000) | $36.00 | $7.39 | $24.84 | $15.84 | $18.00 |
| `a3-highgpu-8g` (8×H100) | $88.49 | $37.92 | $61.38 | $38.86 | $38.32 |
| `a3-ultragpu-8g` (8×H200) | $84.81 | $42.25 | $58.47 | $37.21 | $42.40 |
| `a4-highgpu-8g` (8×B200) | N/A | $34.24 | $88.93 | $56.71 | $64.44 |

> CUD discounts on A3 are deeper than generic GCP tiers: ~31% (1-yr) and ~56% (3-yr) off on-demand. Spot offers ~50–57% off but is preemptible. DWS flex-start gives time-boxed, queued blocks — well-suited to batch scan runs.

### 24×7 monthly (~730 hr) — for reference only; not recommended

| Instance | On-demand | Spot | 1-yr CUD | 3-yr CUD |
|---|---|---|---|---|
| `a3-ultragpu-8g` (H200) | ~$61,900 | ~$30,840 | ~$42,680 | ~$27,160 |
| `a3-highgpu-8g` (H100) | ~$64,600 | ~$27,680 | ~$44,810 | ~$28,370 |
| `g4-standard-384` (RTX PRO 6000) | ~$26,280 | ~$5,395 | ~$18,130 | ~$11,560 |

### Ephemeral / per-scan economics (recommended)

Red-teaming does not require a persistent endpoint. Billed only during actual scan hours, on `a3-ultragpu-8g` (H200) at $84.81/hr on-demand:

| Scan hours/month | On-demand | Spot ($42.25/hr) |
|---|---|---|
| 20 hr | ~$1,696 | ~$845 |
| 40 hr | ~$3,392 | ~$1,690 |
| 80 hr | ~$6,785 | ~$3,380 |

Costs above are compute only — exclude persistent disk, egress, premium OS images, and managed-service (Vertex) charges.

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

*Generated 2026-06-15. Pricing grounded in Google's official accelerator-optimized price sheet (us-central1). Re-verify against the GCP pricing calculator before budgeting.*
