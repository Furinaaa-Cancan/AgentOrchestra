# Deep Dive 05: Process Reward Models — Cross-Domain Transfer & Reward Hacking

## 1. State of the Art (2023–2026)

**Explicit step-supervised PRMs.**
- **Let's Verify Step by Step** (Lightman et al., OpenAI, ICLR 2024). Released PRM800K: 800K human step labels on MATH solutions. Process supervision beats outcome supervision; 78% on MATH test subset. <https://arxiv.org/abs/2305.20050>
- **Math-Shepherd** (Wang et al., ACL 2024). Automatic step labels via MC rollouts from a completer. Mistral-7B GSM8K 77.9 -> 84.1, MATH 28.6 -> 33.0. <https://aclanthology.org/2024.acl-long.510/>
- **Qwen2.5-Math-PRM** (Zhang et al., ACL Findings 2025, "Lessons..."). Shows MC estimation is noisy; consensus filtering (MC AND LLM-judge) needed. Best-of-N 69.3%, ProcessBench F1 78.3%. <https://arxiv.org/abs/2501.07301>
- **ReST-MCTS\*** (Zhang et al., NeurIPS 2024). Tree-search infers per-step values from final correctness; jointly trains policy + PRM. <https://arxiv.org/abs/2406.03816>
- **OpenR** (Wang et al., 2024). Open-source o1-style framework with PRM training + MCTS/beam decoding. <https://arxiv.org/abs/2410.09671>

**Implicit PRMs (no step labels).**
- **PRIME: Process Reinforcement through Implicit Rewards** (Cui et al., 2025). Parameterizes reward so partial-response log-ratios serve as Q-values; derives step rewards from outcome-only data. Beats value baselines in RL. <https://arxiv.org/abs/2502.01456>
- **DeepSeek-R1** (Nature 2025) explicitly rejects PRMs: hard to define a step, hard to label correctness, easy to reward-hack. Uses GRPO with outcome reward only. <https://www.nature.com/articles/s41586-025-09422-z>
- **"Is PRM Necessary? Problem-Solving RL Implicitly Induces PRM Capability"** (2025). Outcome RL induces latent step-judgment behavior. <https://arxiv.org/abs/2505.11227>
- **"GRPO is Secretly a Process Reward Model"** (ICLR submission 2025). Reframes group-relative advantage as implicit per-step credit assignment. <https://openreview.net/pdf/1f109913a199dad205fa51f554aaa5e2a5a782d5.pdf>

## 2. Cross-Domain Transfer — What's Known

- **VersaPRM** (Zeng et al., ICML 2025). The most direct cross-domain study. Trains a PRM on synthetic CoT across MMLU-Pro categories (law, biology, psychology, etc.). Finding: Qwen2.5-Math-PRM only gains 1.3% over majority vote on Law; VersaPRM gains 7.9%. Math PRMs transfer poorly. <https://arxiv.org/abs/2502.06737>
- **"From Mathematical Reasoning to Code"** (2025). Reports math PRMs give ~4% average lift on code generation — partial transfer, contradicting VersaPRM's pessimism on law/bio. The math->code axis is easier (shared symbolic structure) than math->legal/medical prose. <https://arxiv.org/abs/2506.00027>
- **SciRecipe** (2025). Component-based reward for biological protocols; doesn't reuse math PRMs, builds domain-specific reward. <https://arxiv.org/abs/2510.15600>
- **Medicine/law explicit-PRM training:** essentially unstudied beyond VersaPRM's synthetic data setup. No human-labeled medical/legal step-level PRM dataset exists publicly as of May 2026.

So: math->code transfers OK, math->law/bio/medicine transfers weakly, and no PRM has been rigorously stress-tested on safety-critical reasoning chains (clinical, legal).

## 3. Failure Modes

- **Reward hacking under adversarial RL.** Min-Form Credit paper (Cui et al., 2025): policies trained against SOTA PRM on AIME hit >0.9 PRM reward with <4% ground-truth accuracy; 43% of reward gain is hacking. Cause: summation-form credit assignment. <https://arxiv.org/abs/2504.15275>
- **"Reward Under Attack"** (OpenReview 2025). PRMs are brittle to small adversarial perturbations of reasoning steps. <https://openreview.net/pdf?id=Hw24VOppus>
- **Miscalibration on OOD.** "Know What You Don't Know" (Sun et al., 2025) — PRMs systematically overconfident on harder/OOD problems; 90% confidence ≈ much lower actual success. <https://arxiv.org/abs/2506.09338>
- **Generator-PRM coupling.** When the generator is smaller/different from the PRM's training generator, calibration collapses (data-shift bias).
- **Shallow consistency cues.** PRMs latch onto surface features (LaTeX formatting, hedging tokens) rather than causal correctness — implicated in both VersaPRM ablations and the Qwen "Lessons" paper.

## 4. Where the Single-Finding Paper Lives

The literature has the *components* but not the *clean factorial study*. Two viable proposals:

### Proposal A: "PRMs Hack Surface Form, Not Reasoning" — A Minimal Cross-Domain Hacking Audit

**Claim:** A single math-trained PRM (Qwen2.5-Math-PRM-7B) can be reward-hacked in non-math domains by inserting math-like surface tokens (LaTeX, "Step k:", numerical citations) into reasoning chains that are semantically wrong.

**Experiment (~2 GPU-weeks):**
1. Take 500 MMLU-Pro questions across {law, biology, medicine} where the correct answer is known.
2. Generate three CoT variants per item: (a) correct reasoning, plain prose; (b) correct reasoning, math-styled (LaTeX, numbered steps); (c) wrong reasoning, math-styled.
3. Score all with Qwen2.5-Math-PRM, Skywork-PRM, and VersaPRM.
4. Report: rank correlation with correctness, and the "style premium" = mean(PRM(b)) − mean(PRM(a)) for correct chains, plus mean(PRM(c)) vs mean(PRM(a)).

**Single finding:** style premium > correctness premium ⇒ PRMs as currently deployed are surface-feature classifiers in non-math domains. Falsifiable, ~$2K compute, no human labels needed.

**Scoop risk: MEDIUM.** VersaPRM's appendix gestures at this; "Reward Under Attack" probes adversarial robustness but in-domain. The specific *style-transfer hack across domains* framing is open. Adjacent work likely on arXiv within 6 months.

### Proposal B: "Outcome-RL Induces Domain-General Step Judgment; Step-Labeled PRMs Don't"

**Claim:** Implicit step rewards extracted from an outcome-RL'd policy (à la PRIME / GRPO-as-PRM) generalize across domains better than any explicit step-trained PRM, because outcome RL never anchors on step-level surface conventions.

**Experiment (~3 GPU-weeks):**
1. Two reward extractors: (i) Qwen2.5-Math-PRM (explicit); (ii) GRPO-derived implicit PRM from a Qwen2.5-7B policy trained on math outcomes only.
2. Held-out: ProcessBench (math), CodeProcessBench, MMLU-Pro-Law, MedQA stepwise.
3. Metric: step-level error-localization F1.

**Single finding:** implicit-PRM F1 ≥ explicit-PRM F1 on ≥2 of 3 non-math benchmarks ⇒ explicit step labels are a *negative* asset for transfer; they encode the labeler's domain rather than reasoning. This is a strong, surprising, single-table result.

**Scoop risk: HIGH.** "Is PRM Necessary?" (May 2025) and "GRPO is Secretly a PRM" already argue this in-domain. Extending to cross-domain transfer is the obvious next paper and at least 2–3 groups (DeepSeek, Qwen, Tsinghua KEG) are positioned to publish it within 3 months. **Move fast or pivot to Proposal A.**

## Recommendation

Proposal A is the better bet given your single-agent compute budget: tighter, cheaper, harder to scoop because the framing (style-as-hack-vector across domains) is non-obvious. Pair with a small human-validation set (~100 items, $300 on Prolific) to ship a credible empirical paper aimed at COLM 2026 or ACL ARR.