# Efficiency / Inference / Systems / Hardware — Landscape Scan (2025–2026)

Scope: research published or accepted at MLSys, OSDI, SOSP, ASPLOS, ISCA, HPCA, NeurIPS, ICLR, ICML (2025–2026), plus production systems with public technical detail. The verdict tag (HOT / EMERGING / SATURATED) is a deliberate honest judgment, not a hedge.

---

## 1. Quantization & compression

- **AWQ / GPTQ successors with Hadamard rotation (QuaRot, SpinQuant)** — ICLR 2025. Rotation-based outlier suppression enables 4-bit weight+activation at near-FP16 quality. (https://arxiv.org/abs/2404.00456)
- **Atom: Low-Bit Quantization for Efficient and Accurate LLM Serving** — MLSys 2024 (still the reference baseline). INT4 W4A4 serving with mixed-precision outlier channels. (https://proceedings.mlsys.org/paper_files/paper/2024/file/5edb57c05c81d04beb716ef1d542fe9e-Paper-Conference.pdf)
- **BitNet b1.58 2B4T + bitnet.cpp** — ACL 2025 / Microsoft. First open-weight, fully-trained ternary 2B model matching FP16 LLaMA; CPU kernels achieve 6.25x speedup. (https://aclanthology.org/2025.acl-long.457/)
- **MOSS: Microscaling FP8 LLM Training with Automatic Scaling** — 2025. Stable end-to-end FP8 training of 70B+ with adaptive per-tile scales. (https://arxiv.org/html/2511.05811v2)
- **INT4 QAT for RL rollouts (LMSYS, 2026)** — engineering report squeezing a 1TB MoE rollout onto a single H200 with W4A16 QAT in the RL loop. (https://www.lmsys.org/blog/2026-01-26-int4-qat/)

Verdict: **HOT for QAT-in-the-loop and FP4 on Blackwell; SATURATED for pure PTQ of dense weights**. Post-training W4A16 of dense models is essentially solved; the frontier is W4A4 activations for batched serving, FP4 numerics with hardware support, and quantization during RL/post-training rather than after.

Open questions:
- Does QAT-during-RL change *which* capabilities degrade (calibration vs reasoning vs tool use)? A controlled QAT-vs-PTQ ablation on the same SFT+RL recipe at fixed bit budget would answer.
- For ternary BitNet: is the "1.58-bit tax" linear in parameters or does it grow super-linearly at >100B? No public scaling law exists past ~3B.

---

## 2. KV-cache management

- **KV Cache Transform Coding (KVTC)** — ICLR 2026. PCA + adaptive quant + entropy coding for 20–40x KV compression. (https://openreview.net/pdf/1cef9774f0f0cf7bb9e4b167882e3ad3ef8cde16.pdf)
- **TurboQuant / PolarQuant / QJL** — ICLR 2026 + AISTATS 2026 (Google). Quantized Johnson-Lindenstrauss projections for KV with formal error bounds. (https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)
- **ApertureKV: coverage-optimizing eviction** — under review ICLR 2026. Diagnoses an "echo chamber" failure mode in H2O/SnapKV-style eviction and fixes via coverage objective. (https://openreview.net/forum?id=W6aYwEA7i3)
- **KVCompose: attention-guided composite tokens** — layer-adaptive structured compression. (https://openreview.net/pdf?id=GNKIV7oSl2)
- **Marconi: prefix caching for hybrid (SSM+attention) LLMs** — 2025 Amazon. Extends radix prefix caching to recurrent state. (https://assets.amazon.science/96/d4/ee6df8f84a34b49a71f9c39212f2/marconi-prefix-caching-for-the-era-of-hybrid-llms.pdf)

Verdict: **HOT — the most genuinely open frontier in this slice.** Eviction methods (H2O, SnapKV) have known systematic failure modes; transform coding and structured low-rank approaches are still finding the Pareto frontier. Hybrid-arch caching is brand new.

Open questions:
- Eviction methods optimize per-layer reconstruction but accuracy is measured end-to-end; does any single eviction policy survive multi-turn agentic traces with tool calls (>50 turns)? Probably not — a benchmark + diagnosis paper is wide open.
- Can KV compression be made **task-aware at runtime** by reading a few early decoder tokens, rather than fixed at prefill? One-finding paper shape.

---

## 3. Speculative decoding & parallel generation

- **EAGLE-3** — NeurIPS 2025. Multi-layer feature fusion + training-time test; ~6x speedup at batch 1. (https://arxiv.org/abs/2503.01840)
- **P-EAGLE: parallel speculative decoding in vLLM** — AWS 2026. Multi-draft trees scheduled in parallel. (https://aws.amazon.com/blogs/machine-learning/p-eagle-faster-llm-inference-with-parallel-speculative-decoding-in-vllm/)
- **L-MTP: Leap Multi-Token Prediction** — NeurIPS 2025. MTP heads predict non-adjacent positions. (https://github.com/Xiaohao-Liu/L-MTP)
- **Multi-token prediction drafters for Gemma 4** — Google production deployment, 2026. (https://blog.google/innovation-and-ai/technology/developers-tools/multi-token-prediction-gemma-4/)

Verdict: **SATURATED at low batch size; OPEN at high batch.** EAGLE-3 + MTP heads is effectively the ceiling at batch 1. Crucially, *speculative decoding stops helping* once continuous batching saturates compute — the gains vanish at the operating points production cares about. The recent literature increment is small (1.1–1.4x over EAGLE-2).

Open questions:
- Under what concrete batch / arrival-rate regime does spec-decoding become **net negative** (verification overhead > savings)? A clean scheduling-aware characterization across MoE vs dense is missing.
- Can spec-decoding be co-designed with disaggregated decode so drafting runs on cheaper hardware? Hinted at, never measured end-to-end.

---

## 4. Serving systems

- **DistServe** — OSDI 2024. Founding paper for prefill/decode disaggregation; still the throughput-vs-SLO reference. (https://llmsystem.github.io/llmsystem2025spring/assets/files/llmsys-24-disaggregating_prefill_decode_hao_zhang-c0e55139d20512a2348783423397cc7f.pdf)
- **MegaScale-Infer** — SIGCOMM 2025. Disaggregated *expert* parallelism for MoE; separates attention from FFN expert pools. (https://dl.acm.org/doi/10.1145/3718958.3750506)
- **MoE-Lightning** — ASPLOS 2025. Memory-constrained MoE inference with CPU-GPU pipelining; up to 10.3x throughput. (https://dl.acm.org/doi/10.1145/3669940.3707267)
- **DuetServe** — 2025. Reunifies prefill+decode adaptively when disaggregation overhead exceeds benefit. (https://arxiv.org/pdf/2511.04791)
- **vLLM Router** — 2025. Prefill/decode-aware load balancer derived from SGLang gateway. (https://vllm-project.github.io/2025/12/13/vllm-router-release.html)

Verdict: **HOT for MoE serving and PD-disaggregation tuning; SATURATED for monolithic dense serving.** The pendulum is already swinging back — DuetServe shows that PD disaggregation is not universally better, which is the kind of result that opens a new design dimension (adaptive PD).

Open questions:
- Adaptive PD: a control-theoretic policy that re-fuses prefill and decode based on live queue state, with provable SLO bounds. Single paper shape, very tractable.
- MoE expert placement under **skewed expert popularity drift** over hours-long traces — current EP assumes stationary load.

---

## 5. Long-context efficiency

- **FlashAttention-3** — NeurIPS 2024 (still the reference Hopper kernel). FP8 attention at 1.3 PFLOPs/s on H100. (https://arxiv.org/abs/2407.08608)
- **FlashInfer** — MLSys 2025 best-paper candidate. Unified block-sparse KV abstraction; plug-in for vLLM/SGLang/TRT-LLM. (https://homes.cs.washington.edu/~arvind/papers/flashinfer.pdf)
- **Native Sparse Attention (NSA, DeepSeek) / MoBA (Moonshot)** — 2025. Hardware-aligned trainable sparse attention; 1M context with linear-ish cost.
- **RingAttention + StripedAttention successors** for >1M context training — production at xAI/Anthropic, sparse public papers.

Verdict: **HOT — sparse attention has finally become trainable rather than just inference-time.** NSA-style natively-sparse training is the most important shift since FlashAttention.

Open questions:
- Trained-sparse vs trained-dense at matched FLOPs: does sparsity hurt the **specific** capability of needle-in-haystack retrieval at extreme ranges, or only multi-hop synthesis? Unresolved.
- Can FlashInfer-style block-sparse abstractions be exposed in autograd so models *learn* their own block layout? One-finding paper.

---

## 6. Training efficiency

- **FP8 training at 70B+ (MOSS, Megatron-FSDP w/ TE)** — 2025–2026. ~34% throughput over BF16 at parity quality. (https://pypi.org/project/megatron-fsdp/)
- **ZeRO++ / FSDP2 with custom CUDA stream overlap** — PyTorch 2.6+. >83% comm-compute overlap on NVLink. (https://dev-discuss.pytorch.org/t/fsdpv2-communication-overlap-with-compute-will-slow-down-compute-a-lot/3098)
- **Megatron-Bridge / NVIDIA NeMo perf guide** — 2026 reference implementation for 4D parallel + FP8. (https://docs.nvidia.com/nemo/megatron-bridge/latest/performance-guide.html)

Verdict: **SATURATED for dense pretraining; HOT for RL/post-training systems.** Dense pretraining throughput is within 10–15% of hardware peak at the frontier; the action has moved to RL rollouts (long generations, variable length, KV reuse across rollouts).

Open questions:
- RL rollout throughput is dominated by tail latency of long generations — can speculative-rollouts (generate K candidate trajectories, keep the highest-reward) beat single-rollout at fixed compute?
- FP4 *training* (not just inference) — claimed by NVIDIA on Blackwell but no peer-reviewed scaling-law evidence.

---

## 7. Hardware-aware & alt-hardware

- **WaferLLM** — OSDI 2025. Wafer-scale (Cerebras WSE-2) LLM inference; 30–40x over A100+SGLang. (https://arxiv.org/pdf/2502.04563)
- **AI Accelerators for LLM Inference (survey)** — 2025 systematic comparison of Groq LPU, Cerebras WSE-3, SambaNova RDU, TPU v5p/v6, Trainium2. (https://arxiv.org/pdf/2506.00008)
- **PLMR system-software model for wafer-scale** — SIGOPS 2025. Abstract execution model for >100K-core chips. (https://www.sigops.org/2025/wafer-scale-ai-compute-a-system-software-perspective/)

Verdict: **EMERGING — interesting but niche.** Cerebras + speculative decoding hit 4000 tok/s on a 70B; Groq commodity SRAM economics still don't pencil out at long context. The TPU v5/v6 ecosystem is the under-discussed dark horse for cost-per-token.

Open questions:
- Cost-per-quality-token at fixed prompt length: a rigorous third-party benchmark across LPU/WSE/TPU/H200/MI300X is missing (vendor numbers are not comparable).
- Compiler IR for wafer-scale: does PLMR or Pallas-style block IR win for irregular MoE routing?

---

## 8. On-device / edge

- **Apple Foundation Model (3B, on-device)** — Apple ML Research 2025/2026. Matches Qwen-2.5-3B, beats Gemma-3-4B in English. (https://machinelearning.apple.com/research/apple-foundation-models-2025-updates)
- **Phi-4-mini (3.8B) / Phi-4-reasoning** — Microsoft 2025. 88.6% GSM8K on-device. (https://awesomeagents.ai/leaderboards/edge-mobile-llm-leaderboard/)
- **bitnet.cpp** — ACL 2025. Ternary kernels for ARM/x86 CPU. (https://aclanthology.org/2025.acl-long.457/)
- **llama.cpp + GGUF Q4_K_M ecosystem** — de-facto edge runtime; iPhone/Snapdragon NPU offload landing 2026.

Verdict: **HOT — capability per parameter is improving faster than at the frontier.** A 3.8B model passing GSM8K at >85% would have been a 70B result in 2023.

Open questions:
- Sustained-NPU thermal cliff: 2–3 min to throttle on A18 Pro / Snapdragon 8 Elite. No public study measures how *quality* (not just speed) degrades under thermal throttling — quantization may interact with frequency scaling.
- Is there a sub-1B model that genuinely matches 7B on **multi-turn tool use**? All current sub-1B wins are single-turn benchmarks.

---

## Top 5 Open Questions (cross-cutting)

1. **When does speculative decoding go net-negative under realistic continuous batching?**
   *Why open:* every paper benchmarks batch 1; production runs batch 64–256. The crossover regime is folklore, not science.
   *Minimal experiment:* Sweep arrival rate × batch cap × draft length on vLLM with EAGLE-3 on Llama-3-70B; identify the iso-throughput contour where spec-decoding stops helping. One plot, one paper.

2. **Does KV-cache eviction silently fail on long agentic tool-use traces?**
   *Why open:* H2O/SnapKV/ApertureKV are evaluated on summarization and NIAH, not 50-turn tool-calling agents where attention patterns are radically different.
   *Minimal experiment:* Run a fixed agent benchmark (SWE-bench Verified, τ-bench) with each eviction policy at 50%/25%/10% budgets; correlate per-turn attention coverage with task success. Expected finding: eviction is fine until tool-output tokens get evicted, then catastrophic.

3. **Adaptive prefill–decode (re)fusion with provable SLO bounds.**
   *Why open:* DistServe (disaggregate) and DuetServe (re-fuse) are both right at different load levels; nobody has a controller that switches online.
   *Minimal experiment:* MDP formulation with queue length + SLO budget as state; train via simulation on ShareGPT traces; deploy on vLLM. Compare against static disaggregation at 5 load levels.

4. **Quantization × RL post-training interaction.**
   *Why open:* INT4 QAT is now in the RL loop (LMSYS), but no controlled study isolates what RL with quantized rollouts does to specific capabilities vs full-precision RL then PTQ.
   *Minimal experiment:* Fix base model + RL recipe; produce four checkpoints (BF16-RL→FP16, BF16-RL→INT4 PTQ, INT4-QAT-RL, INT4-QAT-RL with FP16 critic); evaluate on MATH, IFEval, τ-bench. One ablation table.

5. **Trained-sparse attention's blind spots at extreme context.**
   *Why open:* NSA/MoBA show parity at 128K on standard benchmarks, but sparse-by-construction models may have systematic deficits on long-range multi-hop synthesis that current benchmarks don't measure.
   *Minimal experiment:* Train two matched 7B models (dense vs NSA-sparse) at 1M context; evaluate on a new multi-hop-at-distance benchmark (e.g., 5 facts placed at random positions across 800K tokens, requiring composition). Predicted finding: NSA matches on retrieval, lags on composition.
