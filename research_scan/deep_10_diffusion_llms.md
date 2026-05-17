# Deep Dive 10: Diffusion LLMs — Real Competition or Niche?

## Direct Execution

### 1. State of the field, 2024–2026

**SEDD (Stanford, ICML 2024 Best Paper).** Lou, Meng, Ermon. Score-entropy loss for discrete diffusion. Beat GPT-2 on zero-shot perplexity at matched size; ~25–75% perplexity reduction over prior discrete-diffusion baselines; competitive generative perplexity vs un-annealed GPT-2 (~6–8x better). Small scale (~300M). [arXiv 2310.16834](https://arxiv.org/abs/2310.16834)

**MDLM (Sahoo et al., NeurIPS 2024).** "Simple and Effective Masked Diffusion LMs" — cleaned-up masked diffusion ELBO; the standard recipe most 2025 work builds on. [arXiv 2406.07524](https://arxiv.org/abs/2406.07524)

**LLaDA 8B (Renmin U. + Ant Group, NeurIPS 2025 Oral).** First serious scaling claim: 8B params, 2.3T tokens, full SFT. Reported parity with LLaMA-3 8B Base on most tasks, advantages on math/Chinese and the reversal curse (reversal-poem completion). Open weights. [arXiv 2502.09992](https://arxiv.org/abs/2502.09992) · [code](https://github.com/ML-GSAI/LLaDA)

**Dream 7B (HKU NLP, 2025).** Trained from an AR initialization (Qwen2.5-7B) with masked-diffusion objective — pragmatic recipe that avoids the from-scratch compute tax. [HKU blog](https://hkunlp.github.io/blog/2025/dream/)

**Mercury / Mercury 2 (Inception Labs).** Closed, commercial. Mercury Coder Mini/Small hit ~1109 / 737 tok/s on H100, claim ~10x speedup vs speed-optimized AR frontier at "comparable quality," tied 2nd on Copilot Arena (above GPT-4o Mini, Gemini-1.5-Flash). Strong on Fill-In-the-Middle. Mercury 2 (Feb 2026) extends to reasoning. [arXiv 2506.17298](https://arxiv.org/abs/2506.17298) · [Inception blog](https://www.inceptionlabs.ai/blog/introducing-mercury)

**DiffuCoder 7B (Apple, 2025).** Continual-pretrained from Qwen2.5-Coder on 400B code tokens + coupled-GRPO. Roughly matches Qwen2.5-Coder and OpenCoder on HumanEval/MBPP/BigCodeBench. [arXiv 2506.20639](https://github.com/apple/ml-diffucoder) · [Dream-Coder 7B, arXiv 2509.01142](https://arxiv.org/abs/2509.01142)

**Scaling reality check.** Controlled IsoFLOP studies (Nie et al.; "Scaling Beyond MDM"; "Scaling Behavior of Discrete Diffusion LMs") show MDMs scale as a power law with slope similar to AR, but need **~16x more compute** to match AR validation loss under standard ELBO; low-variance losses close most of the gap. [arXiv 2603.22075](https://arxiv.org/html/2603.22075v1) · [arXiv 2605.13026](https://arxiv.org/html/2605.13026)

### 2. Where diffusion LLMs actually win

- **Throughput at inference.** Parallel denoising trades depth (NFEs) for width; Mercury's 700–1100 tok/s is the cleanest demonstration. Speedup is real on GPU-bound workloads with short outputs.
- **Infilling / FIM / structured edits.** Bidirectional context is native — no awkward suffix-prefix reordering. DiffuCoder and Mercury both lead AR baselines on FIM.
- **Controllability.** Classifier-free guidance and conditional masking give a knob AR doesn't have; SEDD demonstrated controllable infilling without finetuning.
- **Reversal / non-causal reasoning.** LLaDA's reversal-poem result is the only genuinely architectural win — AR is provably handicapped on left-to-right asymmetric facts.

### 3. Where they lose, honestly

- **Train compute.** ~12–16x AR cost to reach the same loss. Brutal.
- **Long context inference cost.** Each denoising pass re-attends the full context. Long-context per-token cost grows roughly *steps × tokens*, erasing the parallelism advantage past a few thousand tokens. [Goedecke writeup](https://www.seangoedecke.com/limitations-of-text-diffusion-models/)
- **Instruction-following at scale.** LLaDA closes most of the gap post-SFT but still trails AR on MT-Bench-style judge evals; no diffusion model has matched GPT-4-class chat quality yet.
- **KV-cache.** AR's killer optimization doesn't transfer cleanly; recent work (block-diffusion, semi-AR) is the workaround.
- **Reasoning / CoT.** Until Mercury 2 (Feb 2026) there was no production diffusion reasoning model, and its public eval coverage is thin.

### 4. Hybrids — the actually interesting frontier

- **Planned Diffusion (MIT, 2025).** AR plan + diffusion spans. 1.27–1.81x speedup on AlpacaEval at <5.4% win-rate drop. [arXiv 2510.18087](https://arxiv.org/abs/2510.18087)
- **TiDAR (NVIDIA, Nov 2025).** Diffusion drafts, AR verifies, single forward pass; matches Qwen on GSM8K/HumanEval/MMLU with higher tok/NFE. [MarkTechPost](https://www.marktechpost.com/2025/11/13/nvidia-ai-introduces-tidar-a-hybrid-diffusion-autoregressive-architecture-for-high-throughput-llm-inference/)
- **ReFusion (Dec 2025).** Diffusion plans slots, AR infills — explicitly structured-code oriented. [arXiv 2512.13586](https://arxiv.org/html/2512.13586v1)
- **Block / semi-AR diffusion.** Generates blocks AR-style, denoises within block — recovers KV-cache.

The pattern is clear: **pure diffusion at parity is hard; hybrids dominate the Pareto frontier.**

## Paper Opportunities

### Proposal A — Controllability Audit: What Does Diffusion Actually Buy?
Most diffusion-LLM papers chase MMLU parity. The genuine advantage is **structural controllability**: constrained decoding, length control, FIM, regex/grammar masks, reversal facts. Build a benchmark (call it `ControlBench`) covering: (i) JSON-schema adherence under hard constraints, (ii) bidirectional fact recall (reversal curse), (iii) length-targeted generation, (iv) multi-span infilling under shared constraints. Compare LLaDA, Dream, DiffuCoder vs AR at matched size with the same constrained-decoding library. **Why it's accessible:** open weights exist (LLaDA-8B, Dream-7B, DiffuCoder-7B), inference fits on 1–2 H100s, no training needed. This is a measurement paper a small lab can ship. **Risk:** if diffusion only wins on reversal and FIM, that's still a clean finding.

### Proposal B — Diffusion-as-Latent-CoT for Code Agents
AR reasoning is serial token CoT. Diffusion offers **non-causal latent revision**: iterate over a draft, refining globally. Hypothesis: for *code-repair* tasks (SWE-bench-Lite style), diffusion's edit-in-place is a better inductive bias than AR's "rewrite from scratch." Concrete experiment: fine-tune DiffuCoder-7B on SWE-bench train, compare against Qwen2.5-Coder-7B at matched FLOPs and matched inference budget. Specifically measure whether diffusion's iterative refinement reduces the "phantom edit" failure mode (rewriting unrelated lines) that plagues AR coders. Ties directly into your existing experiment v3 infrastructure. **Accessibility:** one fine-tune run + your existing SWE-bench harness. **Honest caveat:** if Mercury 2 has internal data on this, you may be scooped; mitigation is the open-weights and reproducibility angle.

## Deep Interaction (Honest Challenge)

**Is this the next big thing?** Probably not by itself — pure diffusion losing 16x train compute is a structural disadvantage frontier labs won't accept. **Hybrids (TiDAR, Planned Diffusion) are the real story.** They get diffusion's parallelism without abandoning KV-cache.

**Is it accessible for you?** Inference-time work on open LLaDA/Dream/DiffuCoder is genuinely tractable on 1–2 GPUs. Training a competitive diffusion LLM from scratch is not — budget that path out. Proposal A is a 4–8 week paper; Proposal B leverages infrastructure you already have. Pretraining-scale claims (Proposal C, "compute-matched AR vs diffusion") would replicate work the Stanford/CMU IsoFLOP papers already covered and is **not** worth your compute — skip it. The controllability angle is the under-claimed contribution where a small lab can still plant a flag.

Sources:
- [LLaDA paper (arXiv 2502.09992)](https://arxiv.org/abs/2502.09992)
- [LLaDA code](https://github.com/ML-GSAI/LLaDA)
- [SEDD (arXiv 2310.16834)](https://arxiv.org/abs/2310.16834)
- [MDLM (arXiv 2406.07524)](https://arxiv.org/abs/2406.07524)
- [Mercury technical report (arXiv 2506.17298)](https://arxiv.org/abs/2506.17298)
- [Inception Labs blog](https://www.inceptionlabs.ai/blog/introducing-mercury)
- [Dream 7B blog (HKU)](https://hkunlp.github.io/blog/2025/dream/)
- [DiffuCoder (Apple)](https://github.com/apple/ml-diffucoder)
- [Dream-Coder 7B (arXiv 2509.01142)](https://arxiv.org/abs/2509.01142)
- [AR vs MDM controlled comparison (arXiv 2603.22075)](https://arxiv.org/html/2603.22075v1)
- [Accelerating MDM training (arXiv 2605.13026)](https://arxiv.org/html/2605.13026)
- [Planned Diffusion (arXiv 2510.18087)](https://arxiv.org/abs/2510.18087)
- [ReFusion (arXiv 2512.13586)](https://arxiv.org/html/2512.13586v1)
- [TiDAR coverage (MarkTechPost)](https://www.marktechpost.com/2025/11/13/nvidia-ai-introduces-tidar-a-hybrid-diffusion-autoregressive-architecture-for-high-throughput-llm-inference/)
- [Goedecke: limitations of text diffusion](https://www.seangoedecke.com/limitations-of-text-diffusion-models/)
- [Diffusion LM survey](https://arxiv.org/html/2508.10875v2)
