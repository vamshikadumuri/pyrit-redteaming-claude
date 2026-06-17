# GCP Hosting Cost Analysis — PyRIT Attacker Model Candidates

**Primary candidate: `NousResearch/Hermes-4-70B`.** Compares all five candidate attacker models for the PyRIT red-teaming pipeline (in-loop adversarial generator) on a single basis. Hermes-70B is the recommended primary; the 405B is a high-end ceiling option, not the baseline.

**Serving precision policy:** Smaller models (8B / 24B / 70B) served at **full BF16** — no reason to quantize. **Quantization (FP8/INT4) only for the 405B** (§6).

**Source of weights:** On-prem MLflow → one-time push to GCP (no runtime egress at serve time).

**Pricing provenance:** On-demand, Spot, and Flex-start rates taken directly from Google's official [Accelerator-optimized VM price sheet](https://cloud.google.com/products/compute/pricing/accelerator-optimized) (Compute Engine), `us-central1`, retrieved **2026-06-15**. VRAM/spec from the [GPU machine-types doc](https://docs.cloud.google.com/compute/docs/accelerator-optimized-machines). Hourly rates are compute-only, exclusive of disk/egress/OS-license. Spot is dynamic (~30-day repricing). Re-verify before budgeting.

---

## 1. Recommendation (TL;DR)

- **Primary — Hermes-4-70B (BF16):** balanced pick **2× A100-80** (`a2-ultragpu-2g`) $10.14/hr OD, $5.06 spot. **Cheapest** pick **2× RTX PRO 6000** (`g4-standard-96`) **$9.00/hr OD, $1.85 spot** — subject to the G4 throughput caveat below.
- **Cheapest capable model:** Dolphin **8B**, 1× L4 — $0.71/hr OD, $0.31 spot.
- **Mid-tier:** Dolphin **24B (base)** and **R1-24B**, 1× A100-80 — $5.07/hr OD, $2.53 spot.
- **High-end ceiling — 405B (quantized):** cheapest is FP8 on **8× RTX PRO 6000** (`g4-standard-384`) **$36/hr OD, $7.39 spot** (vs 8× H100 $88.49/$37.92), again subject to the G4 caveat.
- **⚠️ G4 caveat:** RTX PRO 6000 is **PCIe (no NVLink)** + **GDDR7 (~1.8 TB/s, vs HBM 3.3–4.8 TB/s)**. Decode is bandwidth-bound, so throughput is lower and tensor-parallel scaling is weaker — worse the more GPUs you span. **Validate tokens/sec before trusting the savings:** a lower hourly rate that runs slower is not actually cheaper. Mild risk at TP=2 (Hermes), serious at TP=8 (405B).
- **Run pattern:** ephemeral / per-scan. Spot ≈ half price (G4 spot far deeper) but preemptible (~30s) — checkpoint stateful campaigns or use Flex-start.

---

## 2. Master comparison (BF16 unless noted, us-central1, hourly)

Ordered smallest → largest. ⭐ = recommended primary. G4 rows marked ³ carry the throughput caveat.

| Model | Serve | Instance | GPU / VRAM | OD $/hr | Spot $/hr | Cloud Run? |
|---|---|---|---|---|---|---|
| `Dolphin3.0-Llama3.1-8B` | BF16 | `g2-standard-4` **/ Cloud Run** | 1× L4 / 24 GB | $0.71 | $0.31 | ✅ |
| `Dolphin3.0-Mistral-24B` (base) | BF16 | `a2-ultragpu-1g` | 1× A100 / 80 GB | $5.07 | $2.53 | ✅¹ |
| `Dolphin3.0-R1-Mistral-24B` | BF16 | `a2-ultragpu-1g` | 1× A100 / 80 GB | $5.07 | $2.53 | ✅¹ |
| ⭐ `Hermes-4-70B` (balanced) | BF16 | `a2-ultragpu-2g` | 2× A100 / 160 GB | $10.14 | $5.06 | ❌ |
| ⭐ `Hermes-4-70B` (cheapest³) | BF16 | `g4-standard-96` | 2× RTX PRO 6000 / 192 GB | **$9.00** | **$1.85** | ❌ |
| `Dolphin-X1-405B` (balanced) | BF16 | `a3-ultragpu-8g` | 8× H200 / 1,128 GB | $84.81 | $42.25 | ❌ |
| `Dolphin-X1-405B` (cheapest³) | FP8 | `g4-standard-384` | 8× RTX PRO 6000 / 768 GB | **$36.00** | **$7.39** | ❌ |

¹ 24B BF16 (~48 GB) needs Cloud Run's 96 GB RTX PRO 6000 option (exceeds 24 GB L4).
³ **G4 throughput caveat** — see §1 / §4.4. Validate tokens/sec.

---

## 3. Memory footprint (BF16 served)

| Model | Params | BF16 weights | Notes |
|---|---|---|---|
| Dolphin3.0-Llama3.1-8B | 8B | ~16 GB | Fits 1× L4 (24 GB) |
| Dolphin3.0-Mistral-24B | 24B | ~48 GB | Fits 1× A100-80 |
| Dolphin3.0-R1-Mistral-24B | 24B | ~48 GB | Reasoning → heavier KV-cache; A100-80 covers it |
| Hermes-4-70B | 70B | ~140 GB | 2 GPUs: 2× A100-80 (160 GB) or 2× RTX PRO 6000 (192 GB) |
| Dolphin-X1-405B | 405B | ~810 GB | **Quantized to fit — see §6** |

---

## 4. Instance & pricing reference

### 4.1 GPU → machine-type map (answers "where's H200?")

Calculator shows GPU **count** + **host RAM** only — never GPU VRAM. Read VRAM here.

| GPU (VRAM/GPU) | Machine family | Notes |
|---|---|---|
| L4 (24 GB) | `g2-standard-*` | Cheapest single-GPU; also Cloud Run GPU |
| A100 40 GB | `a2-highgpu-*` | Full on-demand |
| A100 80 GB | `a2-ultragpu-*` | Full on-demand |
| **RTX PRO 6000 (96 GB GDDR7)** | **`g4-standard-*`** | **PCIe, no NVLink**; cheapest large-VRAM; Cloud Run's 96 GB option |
| **H100 80 GB** | **`a3-highgpu-*`**, `a3-megagpu-8g` | **H100 only — no H200 here** |
| **H200 141 GB** | **`a3-ultragpu-8g` (only)** | Reservation / Spot / Flex-start |
| B200 | `a4-highgpu-8g` | DWS/spot only |

> **`a3-highgpu` is H100-exclusive.** H200 = `a3-ultragpu-8g` only. Total VRAM = per-GPU VRAM × GPU count.

### 4.2 Cost anchors (us-central1) — official price sheet

| Instance | GPUs | OD $/hr | Spot $/hr | Flex-start $/hr |
|---|---|---|---|---|
| `g2-standard-4` | 1× L4 24 GB | $0.7068 | $0.3108 | — |
| `a2-ultragpu-1g` | 1× A100 80 GB | $5.0688 | $2.5296 | $2.40 |
| `a2-ultragpu-2g` | 2× A100 80 GB | $10.1376 | $5.0591 | $4.80 |
| `g4-standard-48` | 1× RTX PRO 6000 96 GB | $4.4999 | $0.9234 | $2.25 |
| `g4-standard-96` | 2× RTX PRO 6000 192 GB | $8.9999 | $1.8467 | $4.50 |
| `g4-standard-192` | 4× RTX PRO 6000 384 GB | $17.9997 | $3.6934 | $9.00 |
| `g4-standard-384` | 8× RTX PRO 6000 768 GB | $35.9994 | $7.3869 | $18.00 |
| `a3-highgpu-8g` | 8× H100 80 GB | $88.4900 | $37.9191 | $38.32 |
| `a3-ultragpu-8g` | 8× H200 141 GB | $84.8069 | $42.2519 | $42.40 |

All directly from Google's price sheet. Note **G4 spot is exceptionally deep** (~79–80% off OD) vs ~50% for A2/A3.

### 4.3 Cloud Run limits

One GPU/instance: L4 (24 GB) or RTX PRO 6000 (96 GB). No multi-GPU. Viable (BF16) for 8B (L4) and the 24B models (96 GB option); not for 70B (~140 GB, multi-GPU) or 405B.

### 4.4 The G4 throughput caveat (read before choosing G4)

RTX PRO 6000 vs the datacenter GPUs: **PCIe interconnect (no NVLink)** and **GDDR7 memory (~1.8 TB/s)** vs HBM (H100 3.35 TB/s, H200 4.8 TB/s). LLM token generation is dominated by memory bandwidth, so:
- **Per-GPU decode is slower** (less bandwidth).
- **Tensor parallelism scales worse** (PCIe vs NVLink) — degradation grows with GPU count: minor at TP=2 (Hermes-70B), significant at TP=8 (405B).
- **Net:** if G4 runs a scan slower, the per-hour saving partially erodes. **Benchmark tokens/sec on the target config before committing.** Best-case use: throughput-tolerant batch runs where wall-clock isn't critical.

---

## 5. Primary: Hermes-4-70B — serving (BF16, ~140 GB → 2 GPUs)

| Path | Instance | VRAM | OD $/hr | Spot $/hr | Notes |
|---|---|---|---|---|---|
| **Cheapest³** | `g4-standard-96` (2× RTX PRO 6000) | 192 GB | **$9.00** | **$1.85** | Lowest cost; validate throughput (TP=2, milder caveat) |
| **Balanced (default)** | `a2-ultragpu-2g` (2× A100-80) | 160 GB | $10.14 | $5.06 | NVLink/HBM, predictable throughput, full on-demand |
| Fastest | `a3-highgpu-2g` (2× H100-80)² | 160 GB | ~$22.1 | ~$9.5 | Highest throughput; ~2× cost; Spot/Flex-only |

- **Recommended:** start on `g4-standard-96` spot; if throughput is inadequate for your campaign cadence, fall back to `a2-ultragpu-2g`.
- TP=2 over PCIe is the mildest G4 case — the caveat is real but usually tolerable for an attacker LLM.

² derived per-GPU from the 8-GPU SKU; sub-8-GPU A3 = Spot/Flex-only.

---

## 6. High-end ceiling: Dolphin-X1-405B (the only quantized model)

Needs an **8-GPU node** (or 4× for INT4). Quantization warranted here.

| Precision | Footprint | Fit | Instance | OD $/hr | Spot $/hr |
|---|---|---|---|---|---|
| **FP8 (cheapest³)** | ~405 GB | 8× RTX PRO 6000 (768 GB) | `g4-standard-384` | **$36.00** | **$7.39** |
| **INT4 (cheapest³)** | ~205–230 GB | 4× RTX PRO 6000 (384 GB) | `g4-standard-192` | **$18.00** | **$3.69** |
| FP8 | ~405 GB | 8× H100 (640 GB) | `a3-highgpu-8g` | $88.49 | $37.92 |
| BF16 | ~810 GB | 8× H200 (1,128 GB) | `a3-ultragpu-8g` | $84.81 | $42.25 |

- **⚠️ G4 at TP=8 is the worst case for the throughput caveat** (§4.4) — an 810 GB-class model sharded over 8 PCIe GDDR7 cards. Hourly saving is huge (~60% off OD, ~80% off spot vs 8× H100), but decode throughput could be materially lower. **Benchmark before relying on it.**
- BF16 405B does **not** fit 8× RTX PRO 6000 (810 > 768 GB) — H200 only.
- **Cloud Run impossible.** ~$62–65K/month at 24×7 on-demand (H200/H100); G4 cuts that sharply but with the throughput risk.

---

## 7. Compliance

All five are **uncensored fine-tunes** (Dolphin / Hermes) — **none abliterated**. Before deploy:
- **GCE raw compute** → general **AUP**. **Generative AI PUP** governs Google's GenAI *Services*, arguably not self-hosted owned weights — gray area.
- PUP (Jan 2026 refresh) added educational/artistic/journalistic/academic exceptions; **no explicit security-red-teaming carve-out**.
- **Action:** confirm posture with GCP account team / legal before deploy. (Not legal advice.)

---

## 8. Model selection guidance

- **Default to Hermes-70B** — best capability without 8-GPU economics. Try `g4-standard-96` spot first for cost, fall back to 2× A100-80 if throughput lags.
- **8B** for high-volume single-turn fuzzing; **24B base** balanced mid-tier; **R1-24B** for adaptive/multi-turn (Crescendo, TAP) where CoT planning aids escalation.
- **405B** only for a one-off ceiling check — and the only model where you'd quantize.
- **Cost lever order:** spot > G4 (validate throughput) > Flex-start > on-demand. For long stateful campaigns prefer on-demand/Flex-start to avoid losing conversation state to preemption.

---

*Generated 2026-06-15. On-demand + Spot + Flex-start pricing grounded in Google's official accelerator-optimized price sheet (us-central1). G4 figures carry an unvalidated-throughput caveat (§4.4). Re-verify against the GCP pricing calculator before budgeting.*
