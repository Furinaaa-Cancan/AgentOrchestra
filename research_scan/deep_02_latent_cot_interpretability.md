# Deep Dive 02: Interpretability of Latent Chain-of-Thought

**Date:** 2026-05-17
**Thesis under test:** The intersection of (a) latent/implicit CoT and (b) mechanistic interpretability is a near-empty quadrant with a clear single-finding paper opportunity.
**Verdict:** Partially empty. The void is shrinking fast — one published probing study exists, an active SPAR Spring 2026 project is targeting Coconut, and Anthropic/OpenAI have adjacent CoT-faithfulness work. The window for a clean first paper is roughly 3–6 months.

---

## 1. State of latent / implicit CoT (confirmed real, accelerating)

The field is no longer speculative. Four reference points:

- **Coconut** (Hao et al., Meta, Dec 2024). Replaces token-level CoT with the last hidden state fed back as the next input embedding. 99.8% on ProntoQA, 97.0% on ProsQA. Authors claim continuous thoughts encode a *superposition of next steps* (parallel BFS), not a single trajectory. Open weights + code released. arXiv:2412.06769.
- **Huginn-3.5B / Recurrent-depth** (Geiping et al., NeurIPS 2025 spotlight). 3.5B params, 800B tokens, iterates a recurrent block at test time. Reaches reasoning performance of a ~50B dense model. No CoT-specific training data needed. arXiv:2502.05171. **This is the most important open-weights model for probing work.**
- **CODI** (Shen et al., King's College London / Turing, EMNLP 2025). Self-distillation aligns student implicit-CoT hidden state with teacher explicit-CoT. First implicit method to match explicit CoT on GSM8K at GPT-2 scale, 3.1× compression. arXiv:2502.21074.
- **SIM-CoT** (InternLM, ICLR 2026). Adds an auxiliary decoder that supervises each implicit reasoning token against a verbalized step. Fixes the "latent collapse" problem at >4 implicit tokens. +8.2% over Coconut. arXiv:2509.20317. Critically, the auxiliary decoder is itself a built-in probe.
- **Quiet-STaR** (Zelikman et al., 2024) is the early precedent — token-parallel rationales with start/end markers. Authors explicitly note "interpretability of rationales is limited."

Are the thoughts real reasoning? Evidence is mixed. Coconut's BFS-superposition claim is mostly behavioral (accuracy curves, depth-of-search). Geiping et al. show compute-equivalent scaling, which is the strongest non-trivial evidence that something other than memorization is happening. No paper has yet shown a *causal* mapping from latent state to a specific sub-reasoning step.

## 2. Probing/interpretability work ON latent thoughts

Not a complete void — but only one published artifact and it's a negative result:

- **Lu et al., "Latent Chain-of-Thought? Decoding the Depth-Recurrent Transformer"** (arXiv:2507.02199, 2025). Applies logit-lens, a custom "Coda Lens," rank-trajectory analysis, and layer-wise probes to Huginn-3.5B on arithmetic. **Finding: limited evidence of interpretable latent CoT.** Hidden-state interpretability depends jointly on layer index and decoding method; probing is inconsistent across recurrent blocks. This is the closest existing paper to the proposed niche, and it explicitly leaves SAEs, causal interventions, and Coconut-style models on the table.
- **SPAR Spring 2026 project** "Interpreting latent reasoning: methods for understanding continuous chain-of-thought" is recruiting now (https://sparai.org/projects/sp26/recip3J5fnlBXUyFB/). This is direct competition; mentor is not listed in the public excerpt.
- **"Finding Sparse Autoencoder Representations of Errors in CoT Prompting"** (OpenReview oCprwPRqwW). Applies SAEs to *explicit* CoT activations — adjacent, not on latent CoT.
- The M-A-P survey on latent reasoning (arXiv:2507.06203) and "Reasoning Beyond Language" survey (arXiv:2505.16782) both list interpretability/probing as the #1 open problem.

**Net: one published paper (negative), one in-flight student project, zero SAE work on Coconut/CODI/SIM-CoT continuous thoughts.** Private-lab unpublished work almost certainly exists at Anthropic and DeepMind given their SAE infrastructure, but no public artifacts.

## 3. The safety angle — sharp and underwritten

Anthropic's "Reasoning models don't always say what they think" (April 2025) found Claude 3.7 Sonnet mentions injected hints only 25% of the time in its CoT; DeepSeek-R1 39%. Unfaithful CoTs are *longer*, not shorter. If verbalized CoT is already this leaky, **latent CoT removes the channel entirely.**

OpenAI + Apollo Research "Chain of Thought Monitorability" (arXiv:2507.11473) explicitly warns the monitorability property is "fragile to changes in training procedure" and singles out outcome-based RL scaling as the failure mode. Latent CoT architectures are the structural realization of that failure mode — they *train away* the verbalization. No paper has yet connected these two literatures.

## 4. The lab position tension

There is a published, citable tension nobody has named:

- OpenAI (Baker et al., Apollo collab) and Anthropic (Chen, Benton et al.) are publicly committed to CoT-monitoring as a load-bearing safety affordance for the 2026–2028 window.
- Meta/FAIR (Coconut), ETH/Maryland (Geiping recurrent-depth), InternLM (SIM-CoT), KCL/Turing (CODI) are publishing efficiency-motivated architectures that destroy monitorability *by design*.

A position paper titled roughly **"Latent Reasoning Breaks the Monitorability Safety Case"** would be cited. But position papers don't land top venues without empirics.

## 5. The research opportunity — two concrete papers

### Paper A (workshop-ready, ~6 weeks): "Logit-Lens and SAEs on Coconut Continuous Thoughts"

- **Model:** facebookresearch/coconut checkpoint (Meta, MIT license) on ProsQA + GSM8K-Aug. Open weights, GPT-2 / LLaMA scale — runnable on a single H100.
- **Method:** (i) Decode each continuous thought vector via logit-lens and tuned-lens; measure top-k token entropy and whether the decoded distribution corresponds to *intermediate* answer tokens of the matched explicit-CoT trajectory. (ii) Train an SAE on the continuous-thought stream (~10k examples × 6–12 thought vectors each). (iii) Run activation patching: replace thought vector *i* from problem A into problem B; measure causal effect on final answer.
- **Minimal claim:** Coconut's continuous thoughts are *decomposable* into a small set of SAE features that causally route the BFS. OR the negative version: continuous thoughts are diffuse and not decomposable into monosemantic features, falsifying the "superposition of next steps" interpretation.
- **Either result is publishable.** Negative result lands at ICLR BlogPost/Mechanistic Interpretability workshop. Positive result + causal intervention lands at NeurIPS main.
- **Differentiator from Lu et al. (2507.02199):** they did Huginn (recurrent-depth, no explicit thought-vector boundary), only logit-lens, no SAE, no causal patching. Coconut has discrete thought slots that make probing cleaner.

### Paper B (main-track ambition, ~4 months): "Steering Latent Reasoning: A Monitorability Probe for Implicit CoT"

- **Models:** Coconut + SIM-CoT + a recurrent-depth checkpoint (Huginn). Three architectures, one method.
- **Method:** Train a linear probe on continuous thoughts to predict (a) the final answer early, (b) presence of a deceptive/sandbagging shortcut on a constructed benchmark (port Anthropic's hint-injection setup from "Reasoning models don't say what they think" to latent CoT). Then *steer*: add the probe direction back into the thought stream and measure whether you can suppress the shortcut.
- **Minimal claim:** A 1-D linear probe on latent thoughts recovers >70% of the safety signal that verbalized CoT monitoring provides on the same hint-injection benchmark — i.e., **latent CoT is not actually opaque to a trained adversary, and the monitorability safety case can be partially salvaged via probing.**
- **Why it lands:** unifies the latent-reasoning architecture community with the CoT-faithfulness/monitorability safety community. First paper to do this. Cites Hao, Geiping, Baker, Chen, Korbak.
- **Risk:** SPAR Spring 2026 project may publish first. Mitigate by scoping to the hint-injection / monitorability framing (safety angle), which the SPAR description does not emphasize.

## Honest caveats

- Anthropic's interpretability team has internal SAE pipelines and Coconut-replication capacity; assume ~30% probability they have unpublished results in this exact direction. Publishing fast matters.
- The Lu et al. negative result on Huginn is a warning that probing recurrent-depth models may genuinely not work cleanly. Coconut's discrete thought-vector structure is the more tractable target — start there.
- "Latent CoT" terminology is still fluid (implicit CoT, continuous CoT, latent reasoning, hidden reasoning). Title carefully.

---

## Sources

- Hao et al., Coconut: https://arxiv.org/abs/2412.06769
- Geiping et al., Recurrent-depth: https://arxiv.org/abs/2502.05171
- Shen et al., CODI: https://arxiv.org/abs/2502.21074
- InternLM, SIM-CoT: https://arxiv.org/abs/2509.20317
- Zelikman et al., Quiet-STaR: https://arxiv.org/abs/2403.09629
- Lu et al., Latent CoT? Depth-Recurrent probe: https://arxiv.org/abs/2507.02199
- M-A-P, Survey on Latent Reasoning: https://arxiv.org/abs/2507.06203
- Reasoning Beyond Language survey: https://arxiv.org/abs/2505.16782
- Chen/Benton et al. (Anthropic), Reasoning models don't say what they think: https://www.anthropic.com/research/reasoning-models-dont-say-think
- Anthropic, Measuring Faithfulness in CoT: https://www.anthropic.com/research/measuring-faithfulness-in-chain-of-thought-reasoning
- Korbak et al. (OpenAI/Apollo/UK AISI et al.), CoT Monitorability: https://arxiv.org/html/2507.11473v2
- OpenAI, Evaluating CoT monitorability: https://openai.com/index/evaluating-chain-of-thought-monitorability/
- SPAR Spring 2026 latent-reasoning interp project: https://sparai.org/projects/sp26/recip3J5fnlBXUyFB/
- SAE on explicit CoT errors (OpenReview): https://openreview.net/forum?id=oCprwPRqwW
- Coconut code: https://github.com/facebookresearch/coconut
- SIM-CoT code: https://github.com/InternLM/SIM-CoT
