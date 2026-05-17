# Deep Dive 12: On-Policy Distillation (OPD)

**Question:** OPD is the production-converged distillation recipe behind Qwen3, DeepSeek-V3/R1, and Gemma 2. Has academia caught up, or does industry lead by 12+ months?

**Short answer:** Industry leads by ~12-18 months on engineering recipe and scale; academia leads on diagnosis of failure modes and theoretical framing. The 2026 wave (survey + "phenomenology" papers) is finally closing the gap.

---

## 1. What OPD precisely is (and isn't)

OPD trains a student S on **sequences sampled from S itself**, with the teacher T scoring those sequences token-by-token (typically reverse-KL or a forward-KL variant on top-K teacher support). It is the intersection of:

- **On-policy RL** (student samples its own rollouts → exposure-bias-free) but with O(N) dense per-token supervision instead of O(1) sparse reward (Thinking Machines blog, 2025).
- **Sequence KD / SeqKD** (Kim & Rush 2016) but trajectories come from S, not T → eliminates train/inference distribution mismatch.
- **MiniLLM** (Gu et al., arXiv:2306.08543, ICLR 2024): first to formalize reverse-KL + on-policy correction for LLMs, with policy-gradient estimator, single-step decomposition, teacher-mixed sampling, length normalization.
- **GKD** (Agarwal et al., arXiv:2306.13649, ICLR 2024, DeepMind): generalized JSD with a λ mixing on-policy vs. off-policy data; powers Gemma 2's distillation step before RLHF.

The terminology is unstable: "on-policy distillation," "online KD," "GKD with λ=1," and "RL with dense teacher reward" describe overlapping objects.

---

## 2. Why it works

Three intuitions, only the first is well-proven:

1. **Exposure-bias correction.** Off-policy KD trains on T's distribution but inference samples from S's; small errors compound off the training manifold. Sampling from S closes this gap (MiniLLM §3, GKD §4).
2. **Mode-seeking via reverse KL.** Reverse KL `KL(S‖T)` underestimates rather than overestimates low-prob regions, giving cleaner generation than forward KL's mass-covering. Caveat: this same property is what causes mode collapse (§4).
3. **Dense supervision wins on sample efficiency.** Per-token teacher logits give ~vocab-size bits/step vs. RL's scalar reward. Qwen3 reports ~10× GPU-hour reduction vs. direct RL for equivalent reasoning gains (Qwen3 TR §3.4, arXiv:2505.09388).

Theoretical understanding is still thin. There is no tight bound for when on-policy beats off-policy as a function of T–S capability gap or sequence length.

---

## 3. Production reports (what labs actually ship)

- **Qwen3 (May 2025, arXiv:2505.09388).** Explicit **two-phase Strong-to-Weak**: off-policy distillation first (to seed `/think` and `/no_think` modes), then on-policy phase aligning student logits to Qwen3-32B / Qwen3-235B-A22B via KL. Used for 0.6B–14B dense + 30B-A3B MoE. Claims ~1/10 GPU hours vs. RL, better exploration. This is the cleanest public OPD recipe in 2025.
- **DeepSeek-R1 distill (Jan 2025).** 800K trace SFT on Qwen2.5/Llama3 backbones — this is **off-policy** SeqKD, not OPD strictly. R1's own training uses on-policy RL (GRPO). Subsequent work (Dropbox "re-distill," 2025) reports that adding on-policy RL after SFT distillation gives +10.7 pt on AIME 2024 at 1.5B — i.e., OPD-flavored second stage matters.
- **Gemma 2 (Aug 2024, arXiv:2408.00118).** 2B and 9B pre-trained with **distribution-level distillation** from a larger teacher (next-token replaced with teacher logits over vocab). Post-training adds on-policy distillation between SFT and RLHF: student samples completions, teacher re-scores, KL loss.
- **MiniCPM, Llama 3.1 405B → 70B/8B.** Llama 3.1 paper describes synthetic-data SFT + DPO; the on-policy KD step is not as cleanly isolated as in Qwen3.

Industry convergence point (mid-2025): **off-policy SFT seeding → on-policy KL distillation → RL polish**. This three-stage stack is the de facto standard.

---

## 4. Failure modes (the academic 2026 wave)

The new papers are mostly diagnostic:

- **"Rethinking OPD"** (THUNLP, arXiv:2604.13016): phenomenology + recipe. Documents capacity-gap thresholds where OPD underperforms off-policy.
- **"Revisiting OPD: Empirical Failure Modes and Simple Fixes"** (arXiv:2603.25562): three failure modes — (i) imbalanced token-level supervision, (ii) unreliable teacher guidance on out-of-distribution student prefixes, (iii) tokenizer / special-token mismatch. Fix: **teacher top-K local support matching** (truncated reverse KL over teacher-supported tokens) + top-p rollout + special-token masking → +19.8% over vanilla OPD.
- **"Many Faces of OPD"** (UIUC ULab): collapse trajectory — initial gains, then rollouts grow long, fill with hedging tokens, accuracy crashes.
- **"Stable OPD via Adaptive Target Reformulation"** (arXiv:2601.07155): reverse-KL lacks an explicit knob for mode-seeking intensity → premature mode collapse on reasoning tasks.
- **"KL-Regularized RL is Designed to Mode Collapse"** (arXiv:2510.20817): theoretical — KL regularization with mode-seeking divergences is structurally biased toward collapse, not a tuning artifact.
- **Survey** (arXiv:2604.00626, May 2026): first comprehensive taxonomy.

Common failure pattern: **T–S gap too large** → student's rollouts are too far from T's support → teacher logits become noisy supervision → variance explodes → collapse.

---

## 5. What academia still hasn't nailed

1. **When does OPD beat off-policy KD as a function of (T–S gap, sequence length, task entropy)?** No clean theorem.
2. **Why does Qwen3's two-phase recipe work better than one-phase?** Empirical only.
3. **Optimal λ schedule** (GKD's on/off mix). Hand-tuned in every production report.
4. **Mode collapse on reasoning** — diagnosed in 2026, no robust fix at scale.
5. **Small-model regime (<1B):** essentially no rigorous study. Qwen3-0.6B exists but the ablations aren't public.

Industry lead: ~12-18 months on recipe maturity (the Qwen3 pipeline isn't reproduced cleanly in any open paper). Academia lead: failure-mode characterization (industry reports successes, hides ablations).

---

## 6. Two paper proposals

### Proposal A — "Capacity-Gap Regimes for On-Policy Distillation: A Phase Diagram"
**Claim:** OPD's advantage over off-policy KD is non-monotonic in T–S capacity gap. Below a gap threshold, on-policy is redundant; above it, student rollouts leave T's support and OPD destabilizes.
**Method:** Fix task (math reasoning, code, summarization). Vary T ∈ {7B, 32B, 235B}, S ∈ {0.5B, 1.5B, 7B}. Sweep λ (on/off mix). Measure: (a) final accuracy, (b) teacher-rollout log-prob (support-overlap proxy), (c) gradient variance. Derive an empirical phase diagram with a theoretical sketch via reverse-KL Taylor expansion around the off-policy optimum.
**Why it matters:** Gives practitioners a decision rule for *when* to invest in on-policy phase vs. just longer off-policy SFT. Closes the biggest open question above.
**Feasibility:** ~2-4K GPU-hours on Qwen2.5 family. Single author + compute.

### Proposal B — "Mode Collapse Forensics: A Failure Atlas for OPD on Reasoning Tasks"
**Claim:** The collapse trajectory documented by ULab/THUNLP is one of (at least) four distinct failure modes, each with a different intervention.
**Method:** Reproduce OPD on 6 reasoning benchmarks (GSM8K, MATH, AIME, HumanEval+, LiveCodeBench, ARC-AGI). For each failure: log per-step entropy, KL(S‖T) on rollout tokens, top-K teacher mass on student prefixes, output length distribution, n-gram diversity. Cluster failures. For each cluster, test a targeted fix (truncated reverse-KL, length penalty, importance-weighted off-policy mixing, teacher-prefix anchoring).
**Deliverable:** Open "OPD-Atlas" dataset of failure trajectories + a diagnostic tool that classifies a partially-collapsed run in <100 steps. This is the kind of empirical paper that gets cited by every subsequent OPD work.
**Feasibility:** Mostly engineering. Strong fit for a small lab.

Proposal B is the higher-leverage paper: failure characterization is what's missing, and it positions for a follow-up theory paper.

---

## Citations

- MiniLLM: Gu et al., arXiv:2306.08543 — https://arxiv.org/abs/2306.08543
- GKD: Agarwal et al., arXiv:2306.13649 — https://arxiv.org/abs/2306.13649
- Qwen3 Technical Report: arXiv:2505.09388 — https://arxiv.org/abs/2505.09388
- Gemma 2 Technical Report: arXiv:2408.00118 — https://arxiv.org/abs/2408.00118
- DeepSeek-R1: https://github.com/deepseek-ai/DeepSeek-R1
- Survey of OPD for LLMs: arXiv:2604.00626 — https://arxiv.org/abs/2604.00626
- Rethinking OPD (THUNLP): arXiv:2604.13016 — https://arxiv.org/abs/2604.13016
- Revisiting OPD — Failure Modes and Fixes: arXiv:2603.25562 — https://arxiv.org/abs/2603.25562
- Stable OPD via Adaptive Target Reformulation: arXiv:2601.07155 — https://arxiv.org/abs/2601.07155
- KL-Regularized RL is Designed to Mode Collapse: arXiv:2510.20817 — https://arxiv.org/abs/2510.20817
- Thinking Machines, "On-Policy Distillation" blog (2025) — https://thinkingmachines.ai/blog/on-policy-distillation/
- Many Faces of OPD (UIUC) — https://ulab-uiuc.github.io/OPD_website/
- Dropbox R1 Re-Distill — https://dropbox.github.io/r1_redistill_blogpost/
- HuggingFace TRL GKD Trainer — https://huggingface.co/docs/trl/gkd_trainer
