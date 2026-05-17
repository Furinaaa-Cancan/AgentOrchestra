# Deep Dive 07: Synthetic Data and Model Collapse — State of Evidence and Paper Opportunities

Date: 2026-05-17

## 1. The collapse case (2023–2025)

**Shumailov et al., Nature 2024** ("AI models collapse when trained on recursively generated data") is the canonical reference. Training generative models recursively on their own outputs causes tails of the distribution to disappear; by the ninth generation, an LM prompted about medieval architecture emits lists of jackrabbits. Mechanism: statistical approximation error compounds across generations, then functional approximation error truncates rare events. Applies to LMs, VAEs, GMMs. There is also a 2025 Author Correction tightening some claims (Nature s41586-025-08905-3).

**Alemohammad et al., ICLR 2024** ("Self-Consuming Generative Models Go MAD", arXiv:2307.01850) showed in image models that without sufficient fresh real data each generation, precision *or* recall degrades after a few autophagous loops. They distinguish fully-synthetic, synthetic-augmented-with-fixed-real, and fresh-real loops, with only the last avoiding MADness.

**Dohmatob, Feng, Kempe — "Strong Model Collapse"** (arXiv:2410.04840, ICLR 2025). Using operator-valued free probability theory in a kernel/regression setting, they prove that even ~1% synthetic content can cap scaling: more data stops helping. This is the strongest theoretical claim to date and is what makes the literature uncomfortable, because frontier corpora already contain non-trivial AI-generated content.

## 2. The counter-evidence

**Gerstgrasser, Schaeffer et al., COLM 2024** ("Is Model Collapse Inevitable? Breaking the Curse of Recursion by Accumulating Real and Synthetic Data", arXiv:2404.01413). The Shumailov setup *replaces* the corpus each generation. If instead you *accumulate* synthetic on top of a fixed pool of real, the test error has a finite upper bound independent of iteration count. Across LMs, diffusion models, and VAEs. This is the most important methodological correction to the collapse narrative — replacement, not generation count, is the lever.

**"Collapse or Thrive?"** (Feng, Dohmatob et al., arXiv:2410.16713) tries to reconcile these by varying mixing ratios and verifier quality. Verifier-filtered synthetic improves; unfiltered may not.

**Phi series** (Gunasekar et al. 2023 "Textbooks Are All You Need", arXiv:2306.11644; Phi-3 arXiv:2404.14219; Phi-4 arXiv:2412.08905). Microsoft trained competitive small models predominantly on synthetic GPT-3.5/4-generated "textbook" data. Phi-4 explicitly seeds synthetic generation from curated organic content. Notably, the Phi-4 report admits models trained *only* on synthetic underperform on knowledge-heavy benchmarks and hallucinate more — synthetic helps reasoning, hurts factual recall.

**Synthetic instruction data is well-established**: Self-Instruct (Wang et al. 2022), Evol-Instruct/WizardLM, Distilling Step-by-Step (Hsieh et al. 2023). DeepSeekMath (arXiv:2402.03300) uses CoT/PoT/tool-integrated synthetic instruction tuning, and the DeepSeek-R1 lineage spawned SYNTHETIC-1 (Prime Intellect, 2M reasoning traces). rStar-Math (arXiv:2501.04519) shows small models can master math via self-generated, verifier-filtered reasoning.

## 3. The reconciling picture

Collapse-vs-thrive hinges on four axes:

1. **Replace vs accumulate** (Gerstgrasser). Accumulation bounds error.
2. **Verifier presence** (rStar-Math, DeepSeekMath, SYNTHETIC-1, "Escaping Model Collapse via Synthetic Data Verification" arXiv:2510.16657). When you can check correctness (math, code), synthetic data is approximately monotone-improving.
3. **Generator capability gap**. Distilling from a stronger model is essentially KD and helps; recursive self-training closes the gap and risks collapse.
4. **Domain entropy**. Code and math are low-entropy, verifiable — synthetic dominates. Open-ended factual knowledge is high-entropy, unverifiable — synthetic narrows distributions (the "knowledge collapse" phenomenon, arXiv:2509.04796: fluency survives, facts fail).

Scaling-law machinery for mixtures (DoReMi arXiv:2305.10429, RegMix ICLR 2025, Data Mixing Laws arXiv:2403.16952, ADO arXiv:2410.11820) is mature for *domain* mixtures but has not been systematically applied to a **synthetic-fraction axis crossed with verifier quality**.

## 4. Paper opportunities

### Proposal A: Phase diagram of synthetic data — quality × ratio × generator gap

Train a grid of 160M–1B-parameter LMs on mixtures parameterized by (i) synthetic fraction f in [0, 1], (ii) generator capability gap Δ (use a fixed teacher model run at varying temperatures/quantizations, or use a ladder of teachers Pythia-410M → Llama-3-8B → Llama-3-70B), and (iii) verifier strength v (none, weak self-consistency, strong execution-based for code/math subsets). Measure test loss, calibration, tail coverage (rare-fact recall, OOD perplexity), and downstream accuracy across 5 generations of recursive training. Output: a closed-form fit predicting collapse threshold f\*(Δ, v) extending the Dohmatob bound to verifier-augmented regimes.

Compute estimate: ~30 grid points × 5 generations × 1B-param at 20B tokens each ≈ 3×10^21 FLOPs total, roughly 8k–15k H100-hours. Feasible on a 64-H100 cluster in ~2 weeks. Honest caveat: small enough to be a *signal* paper, but the extrapolation to 70B+ is conjectural and reviewers will say so.

### Proposal B: Failure-mode taxonomy on code/math under recursive synthetic training

Narrower, cheaper, and more publishable on a single-node budget. Take a fixed 7B base (Qwen2.5-Coder or DeepSeekMath-Base). Iteratively SFT on its own generated solutions to HumanEval+/MBPP+/MATH-500, varying (i) verifier strictness (none / unit-test pass / unit-test + property checks), (ii) accumulation strategy (replace, accumulate, accumulate-with-decay), (iii) diversity injection (none / nucleus / multi-temperature ensemble). Across 8 generations, characterize *which* failure modes emerge: lexical mode collapse (repeated identifiers), algorithmic mode collapse (same idiom for all problems), spec drift (passing easier tests, failing harder), or knowledge collapse (loss of rare library APIs). Cross-tabulate with MAST-style error taxonomy used in the user's experiment v3.

Compute estimate: 24 runs × 8 generations × 7B SFT on ~50k examples ≈ 600–900 A100-hours total. Doable in ~10 days on 8 A100s, or ~3 days on 16 H100s. The contribution is the *taxonomy* and the public per-generation checkpoints, not a scaling law.

## 5. Honest assessment

Proposal A is the higher-status paper but its reviewers will ask why the phase diagram should extrapolate beyond 1B params; without an industry partner that question is unanswerable. Proposal B is what a small academic or independent group can actually finish, and it plugs directly into the user's existing MAST taxonomy and SWE-bench infrastructure. If forced to pick one given the compute budget visible in this repo, B dominates.

## Sources

- [Shumailov et al., Nature 2024](https://www.nature.com/articles/s41586-024-07566-y)
- [Nature Author Correction 2025](https://www.nature.com/articles/s41586-025-08905-3)
- [Borji, "A Note on Shumailov et al." arXiv:2410.12954](https://arxiv.org/abs/2410.12954)
- [Dohmatob, Feng, Kempe "Strong Model Collapse" arXiv:2410.04840](https://arxiv.org/abs/2410.04840)
- [Alemohammad et al. "Self-Consuming Generative Models Go MAD" arXiv:2307.01850](https://arxiv.org/abs/2307.01850)
- [Gerstgrasser et al. "Is Model Collapse Inevitable?" arXiv:2404.01413](https://arxiv.org/abs/2404.01413)
- [Feng/Dohmatob et al. "Collapse or Thrive?" arXiv:2410.16713](https://arxiv.org/pdf/2410.16713)
- [Escaping Model Collapse via Verification arXiv:2510.16657](https://arxiv.org/html/2510.16657v1)
- [Knowledge Collapse in LLMs arXiv:2509.04796](https://arxiv.org/html/2509.04796v1)
- [Gunasekar et al. "Textbooks Are All You Need" arXiv:2306.11644](https://arxiv.org/abs/2306.11644)
- [Phi-3 Technical Report arXiv:2404.14219](https://arxiv.org/html/2404.14219v2)
- [Phi-4 Technical Report arXiv:2412.08905](https://arxiv.org/html/2412.08905v1)
- [DeepSeekMath arXiv:2402.03300](https://arxiv.org/html/2402.03300v3)
- [rStar-Math arXiv:2501.04519](https://arxiv.org/html/2501.04519v1)
- [SYNTHETIC-1 (Prime Intellect)](https://www.primeintellect.ai/blog/synthetic-1-release)
- [DoReMi arXiv:2305.10429](https://arxiv.org/abs/2305.10429)
- [Data Mixing Laws arXiv:2403.16952](https://arxiv.org/html/2403.16952v2)
- [Adaptive Data Optimization arXiv:2410.11820](https://arxiv.org/html/2410.11820v1)
- [RegMix, ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/file/5f67d864aae6115374fed7beddd119e0-Paper-Conference.pdf)
