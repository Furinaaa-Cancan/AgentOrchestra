# Reasoning & Agents — Landscape Scan (2025–2026)

Scope: test-time compute, CoT-beyond-CoT, tool/agent use, multi-agent, self-improvement RL on reasoning, reasoning limits, memory & long-horizon reliability. Sibling agents own foundation, alignment, applications, efficiency — not duplicated here.

---

## 1. Test-Time Compute & Reasoning Models

Post-o1/R1, the field has fragmented from "one big CoT" toward verifier-guided search and *generative* process supervision.

- **ThinkPRM** — "Process Reward Models That Think", ICLR 2026 ([OpenReview](https://openreview.net/forum?id=V727xqBYIW)). Verbalized step-wise PRM that emits a verification CoT; trained on orders of magnitude fewer process labels than discriminative PRMs.
- **GenPRM** — arXiv 2504.00891, 2025 ([arXiv](https://arxiv.org/abs/2504.00891)). 7B generative PRM with code-verification CoT; beats Qwen2.5-Math-PRM-72B on ProcessBench via test-time scaling.
- **Rewarding Progress** — NeurIPS 2025 ([OpenReview](https://openreview.net/forum?id=A6Y7AqlzLW)). Defines "progress" as Q-value advantage on a prover policy; principled training signal for automated process verifiers.
- **DeepSeek-R1** — arXiv 2501.12948 ([arXiv](https://arxiv.org/pdf/2501.12948)). GRPO with rule-based rewards only; flagged neural PRMs as reward-hackable at scale — still-unresolved tension with the PRM line above.
- **Trust but Verify** — survey, arXiv 2508.16665 ([html](https://arxiv.org/html/2508.16665v3)). Taxonomizes verifier designs (discriminative, generative, executable, consistency) for TTS.

Verdict: **HOT** — generative/verbalized PRMs are the rising design. **SATURATED**: best-of-N over a frozen scalar verifier.

Open questions:
- Reward-hacking dynamics of *generative* PRMs under long-horizon RL — does GenPRM survive 50k GRPO steps where discriminative PRMs collapsed?
- Cross-domain PRM transfer (math → code → web agents) without per-domain calibration. PRMs are currently siloed.
- Compute-optimal allocation between *generator* tokens and *verifier* tokens at fixed FLOPs — currently ad-hoc.

---

## 2. Chain-of-Thought Beyond CoT (latent / implicit reasoning)

Most exciting structural shift since 2024. ICLR 2026 has a dedicated **LIT workshop** ([site](https://latent-implicit-thinking.github.io/)) — strong emergence signal.

- **Coconut** — ICLR 2025 ([arXiv 2412.06769](https://arxiv.org/abs/2412.06769)). Feeds last hidden state back as next embedding; latent "thought" encodes a superposition of next steps (implicit BFS).
- **SIM-CoT** — ICLR 2026 ([GitHub](https://github.com/InternLM/SIM-CoT)). Step-level supervision on latent thoughts, fixing the instability/scaling cliff Coconut hits past ~6 latent steps.
- **Recurrent-Depth Latent Reasoning** — NeurIPS 2025 ([poster](https://neurips.cc/virtual/2025/poster/117966)). Iterates a recurrent block to arbitrary depth at test time; scales TTC without emitting tokens.
- **Parallel Test-Time Scaling for Latent Reasoning** — arXiv 2510.07745 ([PDF](https://arxiv.org/pdf/2510.07745)). Self-consistency analogue in continuous space.
- **Survey: Reasoning Beyond Language** — arXiv 2505.16782 ([html](https://arxiv.org/html/2505.16782v1)).

Verdict: **EMERGING / HOT** — clearest single bet for a 2026 single-author paper. Token-CoT variants (ToT, GoT, self-consistency) are **SATURATED**; marginal gains only.

Open questions:
- **Interpretability of continuous thoughts**: can we decode a Coconut hidden state into a probability distribution over discrete reasoning trees, and does it match the model's eventual answer?
- **Latent self-consistency**: does ensembling N latent rollouts beat ensembling N token rollouts at matched FLOPs? Evidence is mixed.
- **Failure-mode map of latent reasoning** — nothing systematic yet on arithmetic carry, multi-hop entity tracking, negation under latent CoT.

---

## 3. Tool Use & Agents

Benchmark layer is in crisis (Berkeley April 2026: every major agent benchmark broken by reward hacking, [post](https://rdi.berkeley.edu/blog/trustworthy-benchmarks-cont/)).

- **ToolACE** — ICLR 2025 ([PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/663865ea167425c6c562cb0b6bcf76c7-Paper-Conference.pdf)). Hierarchical API context tree for synthesizing diverse function-call training data.
- **ARTIST** — agentic reasoning + tool integration via outcome RL, multi-turn, no step labels ([Awesome-Agent-Papers](https://github.com/luo-junyu/awesome-agent-papers)).
- **AgentHarm** — ICLR 2025 ([PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/c493d23af93118975cdbc32cbe7323f5-Paper-Conference.pdf)). Robustness/safety of tool-using agents.
- **Berkeley "How We Broke Agent Benchmarks"** ([blog](https://rdi.berkeley.edu/blog/trustworthy-benchmarks-cont/)) — single scanning agent breaks GAIA, OSWorld, WebArena, AgentBench, SWE-bench variants via leaked answers, unsanitized eval(), prompt-injectable judges.
- **Agent Evaluation Survey** — arXiv 2507.21504 ([html](https://arxiv.org/html/2507.21504v1)).

Verdict: **HOT** for tool RL, but benchmark trust is collapsing — the meta-question is hotter than the methods.

Open questions:
- Build a **contamination/exploit-resistant agent benchmark**: procedural task generation, sealed graders, per-run secrets, audited against Berkeley's exploit suite.
- Function-call **argument-level calibration**: do models know when their tool call will fail before issuing it?
- Hierarchical planning *transferable across environments* (OS → web → code) without retraining — every current system overfits one shell.

---

## 4. Multi-Agent Systems — **SATURATED** (flag)

Honest read: multi-agent decomposition for general reasoning has plateaued. Strong single-agent + tools + verifier matches or exceeds debate at lower cost. MAST (Cemri et al., 2025) catalogued 14 failure modes across 1600+ traces.

- **MAST** — failure-mode taxonomy of multi-agent systems, 2025.
- **MAD-M2** (memory masking) — arXiv 2603.20215 ([html](https://arxiv.org/html/2603.20215v1)). Patches erroneous-memory propagation in debate.
- **Adaptive heterogeneous MAD** — Springer 2025 ([link](https://link.springer.com/article/10.1007/s44443-025-00353-3)).
- **MAD for LLM Judges w/ Adaptive Stability** — OpenReview ([forum](https://openreview.net/forum?id=Vusd1Hw2D9)).
- **Should we be going MAD?** — ICML 2024 critique ([PDF](https://raw.githubusercontent.com/mlresearch/v235/main/assets/smit24a/smit24a.pdf)).

Verdict: **SATURATED for general reasoning**. The only live frontier is *role-asymmetric* systems with explicit information control (judges, prediction markets, adversarial verifiers) — not symmetric debate.

Open questions (narrow, still attackable):
- Same-FLOP head-to-head: small verifier + large solo solver vs any debate config. Likely a clean negative result for debate.
- Does debate suppress correct minority views as a function of model homogeneity? Measurable, currently anecdotal.

---

## 5. Self-Improvement & RL on Reasoning

Dominant 2026 recipe.

- **On-Policy Distillation (OPD/OPSD)** — Thinking Machines ([blog](https://thinkingmachines.ai/blog/on-policy-distillation/)); Siyan Zhao 2026 ([link](https://siyan-zhao.github.io/blog/2026/opsd/)). 4–8× token efficiency vs GRPO; in Qwen3, DeepSeek-V4, Gemma 2, MiMo-V2 production pipelines.
- **Survey of On-Policy Distillation** — arXiv 2604.00626 ([html](https://arxiv.org/html/2604.00626)).
- **Self-Distilled RLVR** — arXiv 2604.03128 ([html](https://arxiv.org/html/2604.03128v2)).
- **SRT (Self-Rewarded Training)** — ([site](https://self-rewarding-llm-training.github.io/)). Consistency-based self-supervision; documents **performance-collapse** under prolonged self-reward — canonical reward-hacking cautionary tale of 2025.
- **Self-Evolved Reward Learning** — NeurIPS 2025 ([OpenReview](https://openreview.net/forum?id=Zonhl0c9I0)).

Verdict: **HOT**. OPD has moved from research to standard pipeline.

Open questions:
- **Predicting SRT collapse**: is there an early-warning signal (entropy, reward variance) before pseudo-reward maximization overtakes accuracy?
- OPD applied to **agent trajectories** (not just math CoT) — does the dense per-token KL signal survive long-horizon, tool-using rollouts? Untested.
- Does on-policy distillation **erase diversity** needed for downstream RL exploration? No principled measurement.

---

## 6. Emergent Abilities & Limits

- **In-Context Adaptation for OOD** — ICLR 2026 ([OpenReview](https://openreview.net/pdf?id=f58uDOwLaq)). Finds environment-invariant features to resist shortcuts.
- **Interplay of Pre-Training, Mid-Training, RL** — arXiv 2512.07783 ([PDF](https://arxiv.org/pdf/2512.07783)).
- **Principled Synthetic Logic Corpus** — NeurIPS 2024 ([PDF](https://proceedings.neurips.cc/paper_files/paper/2024/file/8678da90126aa58326b2fc0254b33a8c-Paper-Conference.pdf)).
- ICLR 2026 LLM-Reasoning workshop ([site](https://sites.google.com/view/iclr-2026-llmreasoning)).

Verdict: **EMERGING** — failure-mode cartography is under-supplied relative to capability claims.

Open questions:
- **Premise-order sensitivity** on long-context reasoning models — does o3-class TTC reduce or amplify it? Two-page empirical paper.
- **Compositional disjunction** ("A or B implies C") — LRMs still fail; nobody has cleanly isolated whether the bottleneck is pretraining data, RL reward shape, or representation geometry.
- Does RL **erase** compositional generalization present in the base model? Recent interplay work hints yes.

---

## 7. Memory-Augmented & Long-Horizon Agents

- **Beyond pass@1: A Reliability Science Framework** — arXiv 2603.29231 ([html](https://arxiv.org/html/2603.29231v1)). Reliability degrades **super-linearly** with horizon; pass@1 on short tasks hides this. Across 10 models, memory scaffolds **never** helped at long horizons.
- **Agentic Memory (AgeMem)** — arXiv 2601.01885 ([abs](https://arxiv.org/abs/2601.01885)). Treats store/retrieve/update/summarize/discard as RL-optimizable tools.
- **Continuum Memory Architectures** — arXiv 2601.09913 ([html](https://arxiv.org/html/2601.09913v1)).
- **AMA-Bench** — long-horizon memory eval, arXiv 2602.22769 ([html](https://arxiv.org/html/2602.22769v1)).
- ICLR 2026 **MemAgents workshop** ([proposal](https://openreview.net/pdf?id=U51WxL382H)).

Verdict: **HOT and under-baked** — the "memory doesn't help" finding is the most surprising 2026 result in this area.

Open questions:
- **Why does memory hurt at long horizons?** Isolating retrieval noise vs context dilution vs distractor accumulation would be a top-venue paper alone.
- **Reliability scaling law**: `reliability ~ exp(-α·horizon^β)`? β unknown, fittable from existing released traces.
- Cross-task **lifelong** memory — every benchmark today is in-episode only.

---

## Top 5 Open Questions (cross-cutting picks)

1. **Why does agent memory hurt at long horizons?** (§7) — Pick 2 models, 1 benchmark (AMA-Bench), ablate retrieval noise vs context dilution vs distractor count. Single-finding, ICLR/NeurIPS-shaped, low compute.
2. **Decoding latent thoughts into discrete reasoning distributions** (§2) — Train linear/MLP probes from Coconut/SIM-CoT hidden states to next-step token distributions; test faithfulness to final answer. Cheap, novel, interpretability ↔ reasoning crossover.
3. **Early-warning signal for self-reward collapse** (§5) — Re-run SRT, log per-step reward variance and policy entropy; predict the collapse step before it happens. One GPU-week.
4. **Contamination-resistant agent benchmark** (§3) — Procedural task generation + sealed grader + per-run secrets, audited against the Berkeley exploit suite. High citation ceiling; the community needs this.
5. **Cross-domain PRM transfer** (§1) — Train one GenPRM on math, evaluate zero-shot on code/web/medical reasoning; map the transfer matrix. Currently every PRM is siloed; a transfer paper would set the next agenda.

---

Sources:
- [ThinkPRM (ICLR 2026)](https://openreview.net/forum?id=V727xqBYIW)
- [GenPRM](https://arxiv.org/abs/2504.00891)
- [Rewarding Progress](https://openreview.net/forum?id=A6Y7AqlzLW)
- [DeepSeek-R1](https://arxiv.org/pdf/2501.12948)
- [Verifier survey](https://arxiv.org/html/2508.16665v3)
- [Coconut](https://arxiv.org/abs/2412.06769)
- [SIM-CoT](https://github.com/InternLM/SIM-CoT)
- [Recurrent-Depth Latent Reasoning](https://neurips.cc/virtual/2025/poster/117966)
- [LIT Workshop ICLR 2026](https://latent-implicit-thinking.github.io/)
- [Parallel TTS for Latent Reasoning](https://arxiv.org/pdf/2510.07745)
- [Latent CoT survey](https://arxiv.org/html/2505.16782v1)
- [ToolACE (ICLR 2025)](https://proceedings.iclr.cc/paper_files/paper/2025/file/663865ea167425c6c562cb0b6bcf76c7-Paper-Conference.pdf)
- [AgentHarm](https://proceedings.iclr.cc/paper_files/paper/2025/file/c493d23af93118975cdbc32cbe7323f5-Paper-Conference.pdf)
- [Berkeley broken-benchmarks](https://rdi.berkeley.edu/blog/trustworthy-benchmarks-cont/)
- [Agent eval survey](https://arxiv.org/html/2507.21504v1)
- [MAD-M2](https://arxiv.org/html/2603.20215v1)
- [Should we be going MAD?](https://raw.githubusercontent.com/mlresearch/v235/main/assets/smit24a/smit24a.pdf)
- [On-Policy Distillation (Thinking Machines)](https://thinkingmachines.ai/blog/on-policy-distillation/)
- [OPSD blog](https://siyan-zhao.github.io/blog/2026/opsd/)
- [OPD survey](https://arxiv.org/html/2604.00626)
- [Self-Rewarded Training](https://self-rewarding-llm-training.github.io/)
- [Self-Evolved Reward Learning](https://openreview.net/forum?id=Zonhl0c9I0)
- [In-Context Adaptation OOD (ICLR 2026)](https://openreview.net/pdf?id=f58uDOwLaq)
- [Beyond pass@1 Reliability](https://arxiv.org/html/2603.29231v1)
- [AgeMem](https://arxiv.org/abs/2601.01885)
- [AMA-Bench](https://arxiv.org/html/2602.22769v1)
- [MemAgents Workshop](https://openreview.net/pdf?id=U51WxL382H)
