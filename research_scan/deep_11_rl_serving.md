# Deep Dive #11: RL Rollout Systems & Training Infrastructure (2024-2026)

## 1. Landscape of RL Post-Training Frameworks

The center of gravity in LLM training has shifted from dense pretraining to RL post-training (RLHF, RLVR, RLAIF, agentic RL). The frameworks differ primarily on **how they place models** (colocated vs. disaggregated) and **how they synchronize** (sync vs. async).

| Framework | Origin | Architecture | Notable claim |
|---|---|---|---|
| **veRL / HybridFlow** | ByteDance Seed + HKUST (Sheng et al., 2024) | Hybrid single-controller (control flow) + multi-controller (compute); 3D-HybridEngine for actor resharding between train/gen | 1.5x–20x throughput vs. DSChat/OpenRLHF/NeMo-Aligner; PPO/GRPO/ReMax/Safe-RLHF [arXiv:2409.19256] |
| **OpenRLHF** | Hu et al., 2024 (EMNLP 2025 demo) | Ray + vLLM + DeepSpeed ZeRO-3, **disaggregated** placement of actor/critic/RM/ref | 1.22x–1.68x over DSChat; first prod-ready Ray+vLLM design [arXiv:2405.11143] |
| **NeMo-Aligner -> NeMo-RL** | NVIDIA | Megatron-Core + Ray; Aligner deprecated May 2025, replaced by NeMo-RL | Megatron TP/PP/CP, HF model bridge |
| **TRL** | HuggingFace | Single-process or accelerate; integrates vLLM for rollouts as of 2024 | Reference impl, not a scale-out system |
| **AReaL** | Ant/InclusionAI (Fu et al., May 2025) | Fully decoupled SGLang generation workers + Megatron training; interruptible rollouts, dynamic batching | 2.77x speedup over sync baselines [arXiv:2505.24298] |
| **AsyncFlow** | 2025 | Asynchronous streaming RL | arXiv:2507.01663 |
| **ROLL Flash** | 2025 | Async RLVR + agentic | arXiv:2510.11345 |
| **RLinf** | 2025 | Macro-to-micro flow transformation | arXiv:2509.15965 |
| **RollPacker** | 2025 | Long-tail rollout mitigation for sync RL | arXiv:2509.21009 |

Two design axes dominate publications:
- **Colocated (veRL 3D-HybridEngine)** wins on small/mid models where resharding cost is dominated by GPU memory savings.
- **Disaggregated (OpenRLHF, AReaL)** wins when the rollout engine (vLLM/SGLang) and trainer (Megatron/DeepSpeed) have very different parallelism shapes, or when rollouts dominate wallclock.

## 2. Async vs. Sync Rollout — When Does Async Pay Off?

Noukhovitch et al., **Asynchronous RLHF** (ICLR 2025, arXiv:2410.18252), separated generation and learning so generators produce on stale-by-k policies. Findings:
- ~40% wallclock speedup on LLaMA 3.1 8B instruction-following; ~70% on Rho-1B GSM8k, matched final perf.
- **Online DPO is most off-policy-robust**; PPO degrades faster as staleness grows.
- Robustness to off-policy data **increases with policy size** — async is a "big-model" optimization, marginal for <1B.

AReaL and ROLL Flash extend this with **interruptible rollouts** (kill long-tail trajectories when a new policy ships) and dynamic batching. Async wins precisely when rollout length variance is high (reasoning, agents): the long tail of a single trajectory can stall a sync step for 5–10x median.

When async **doesn't** pay off: short responses (chat-style RLHF with <512 tokens), large reward models that dominate the critical path, or when KL penalties make the policy diverge fast under stale data.

## 3. Rollout-Inference Engine Separation

The 2024–2026 consensus is that **the rollout engine should be a dedicated inference server (vLLM or SGLang)**, not a HuggingFace generate() loop in the trainer process. Patterns:
- **TRL + vLLM** (2024): vLLM server held in a separate process; weight sync over NCCL broadcast each step.
- **OpenRLHF Ray + vLLM** ([vLLM blog, Apr 2025](https://blog.vllm.ai/2025/04/23/openrlhf-vllm.html)): actor weights pushed to vLLM workers, prefix caching across rollouts.
- **veRL 3D-HybridEngine**: same GPUs, but resharded between TP=8 training and TP=2 rollout shapes — zero memory redundancy.
- **Sequence packing**: AReaL and verl both pack variable-length rollout outputs into fixed-shape training batches via cu_seqlens (FlashAttention varlen), eliminating padding waste that used to hit 40–60% on reasoning workloads.

## 4. RL on Long-Horizon Agents

Agentic episodes (SWE-bench tasks, web navigation) take 2–30 min each. Current strategies:
- **Trajectory truncation + bootstrapped value** (NeMo-RL, ROLL Flash): cut at max_length, learn a value head to bootstrap.
- **Step-level vs trajectory-level credit**: GRPO with sparse final reward dominates because value models on long contexts are hard to train.
- **Interruptible workers** (AReaL, ROLL Flash): kill stale trajectories when policy updates; only completed ones contribute.
- **Replay of partial trajectories**: keep tool-call prefixes in a cache, only re-roll from divergence point.

Open: **nobody has a good value model for 10-minute episodes**. GRPO and DPO sidestep it; whether this hurts final performance vs. PPO+V is unresolved.

## 5. Quantization in the RL Loop

**LMSYS SGLang INT4 QAT** (Jan 26, 2026): "Squeezing 1TB Model Rollout into a Single H200" [lmsys.org/blog/2026-01-26-int4-qat](https://www.lmsys.org/blog/2026-01-26-int4-qat/). The claim:
- BF16 master weights on the training side; **fake QDQ** quantization in the forward pass during QAT.
- W4A16 deployed for rollouts; ~1TB Kimi-K2-class model fits a single H200 (141GB).
- **Eliminates cross-node rollout communication** — the dominant async-RL bottleneck at trillion-parameter scale.
- Reports train/infer consistency and final quality matching BF16, inspired by Kimi K2.

This is the most important systems result of 2026 so far for RL: it collapses the rollout-engine footprint by 4x and makes single-node rollout feasible for frontier models.

## 6. Paper Opportunities

### Proposal A: Systematic efficiency benchmark of RL frameworks on a standardized RLVR task
- **Setup**: GSM8k + MATH + a SWE-bench-mini subset; Qwen2.5-7B and 32B; fixed reward function; report tokens/s, GPU-hours-to-target-accuracy, rollout/train ratio, long-tail p99/p50, off-policy staleness.
- **Frameworks**: veRL, OpenRLHF, NeMo-RL, AReaL, TRL+vLLM.
- **Gap addressed**: every paper benchmarks against a strawman; no neutral apples-to-apples exists in 2026.
- **Compute honest**: ~4000 H100-hours for 7B sweep (5 frameworks x 2 algos x ~400h each). 32B sweep is **out of reach** for academia (~30k H100-h); restrict to 7B + one 32B confirmation run. Single-node H200 with INT4 QAT could halve this.

### Proposal B: Characterization of async failure modes
- **Setup**: Sweep staleness k in {1, 2, 4, 8, 16} steps across (model size, algorithm, task horizon). Measure divergence signatures: KL blowup, reward hacking emergence, value-function collapse, gradient norm trajectories.
- **Deliverable**: an empirical "phase diagram" of when async breaks, plus a cheap online detector (KL slope + grad-norm ratio).
- **Gap addressed**: ICLR 2025 async-RLHF paper shows async **works**, but the literature has no characterization of **when and how it silently fails**. Practitioners are flying blind on staleness budgets.
- **Compute honest**: ~2000 H100-hours for a 1B/7B grid; feasible on a small academic cluster or modest cloud budget (~$40-60k at spot rates). Single-node friendly with INT4 QAT.

(Skipped Proposal C "rollout-aware scheduler" — RollPacker arXiv:2509.21009 and ROLL Flash already occupy that lane; marginal novelty.)

## Sources

- [HybridFlow / veRL paper (arXiv:2409.19256)](https://arxiv.org/abs/2409.19256)
- [veRL GitHub](https://github.com/verl-project/verl)
- [OpenRLHF paper (arXiv:2405.11143)](https://arxiv.org/abs/2405.11143)
- [vLLM blog: OpenRLHF integration](https://blog.vllm.ai/2025/04/23/openrlhf-vllm.html)
- [Asynchronous RLHF (ICLR 2025, arXiv:2410.18252)](https://arxiv.org/abs/2410.18252)
- [AReaL (arXiv:2505.24298)](https://arxiv.org/abs/2505.24298)
- [AsyncFlow (arXiv:2507.01663)](https://arxiv.org/pdf/2507.01663)
- [ROLL Flash (arXiv:2510.11345)](https://arxiv.org/pdf/2510.11345)
- [RLinf (arXiv:2509.15965)](https://arxiv.org/html/2509.15965v1)
- [RollPacker (arXiv:2509.21009)](https://arxiv.org/html/2509.21009v1)
- [NeMo-RL docs](https://docs.nvidia.com/nemo/rl/latest/index.html)
- [LMSYS INT4 QAT blog (Jan 26, 2026)](https://www.lmsys.org/blog/2026-01-26-int4-qat/)
- [Anyscale: Open-Source RL Libraries for LLMs](https://www.anyscale.com/blog/open-source-rl-libraries-for-llms)
