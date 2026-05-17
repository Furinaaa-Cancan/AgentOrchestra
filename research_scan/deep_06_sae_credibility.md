# Deep-Dive 06: Sparse Autoencoders — Credibility Crisis & Salvage Paths

## Part 1: Direct Execution

### 1. State of SAE Research (2024–2026)

The arc: Anthropic's *Towards Monosemanticity* (2023) and *Scaling Monosemanticity* (2024, Claude 3 Sonnet, ~34M features incl. "Golden Gate" feature) launched the program. Architectural iterations followed: **Gated SAE** (DeepMind, Rajamanoharan 2024), **TopK SAE** (OpenAI, Gao et al. 2024 — `arxiv.org/abs/2406.04093`), and **JumpReLU SAE** (DeepMind, Rajamanoharan et al. 2024 — `arxiv.org/abs/2407.14435`), which now powers **Gemma Scope** and **Gemma Scope 2** (Sep 2025, all layers of Gemma 3, multi-layer SAEs + skip-transcoders). Anthropic's March 2025 **Circuit Tracing / Attribution Graphs** work (Lindsey et al., `transformer-circuits.pub/2025/attribution-graphs/methods.html`) moved past raw SAEs to **cross-layer transcoders (CLTs)** as a "replacement model" — features that read residual stream and write to all later MLPs, matching base-model outputs ~50% of the time. Marks et al.'s **Sparse Feature Circuits** (ICLR 2025) used SAE features as circuit nodes.

### 2. Critique Papers — Concrete List

The credibility crisis is real and traceable to roughly six papers:

- **Tian, "Measuring Sparse Autoencoder Feature Sensitivity"** (arXiv:2509.23717). Generates text resembling activating examples and tests re-activation. **Many "interpretable" features fail sensitivity audits, and average sensitivity *declines* with SAE width across 7 variants — a negative scaling result.**
- **"Are Sparse Autoencoders Useful? A Case Study in Sparse Probing"** (Kantamneni et al., arXiv:2502.16681, ICML 2025). SAE probes beat linear-probe baselines on only **2.2%** of datasets. Ensembles don't help.
- **DeepMind Safety Research, "Negative Results for SAEs on Downstream Tasks and Deprioritising SAE Research"** (Medium, 2025). Internal team progress update: SAEs underperform linear probes; chat-specialised SAEs close ~½ the gap. **DeepMind explicitly deprioritised SAE research.** This is the single most consequential signal.
- **"Interpretability Illusions with Sparse Autoencoders"** (Zeng et al., arXiv:2505.16004). Tiny adversarial perturbations flip SAE concept activations *without* changing base-LM activations meaningfully. Concept representations are fragile.
- **Song et al., "Position: Mechanistic Interpretability Should Prioritize Feature Consistency in SAEs"** (arXiv:2505.20254). Different runs produce different dictionaries; proposes PW-MCC (Pairwise Dictionary Mean Correlation Coefficient). TopK reaches 0.80, others much lower. Reproducibility crisis in plain sight.
- **"Sanity Checks for Sparse Autoencoders: Do SAEs Beat Random Baselines?"** (arXiv:2602.14111). Several proxy metrics fail to distinguish trained SAEs from random initialisations.

### 3. New Evaluation Rigor

- **SAEBench** (Karvonen et al., arXiv:2503.09532, ICML 2025; `neuronpedia.org/sae-bench`). 200+ SAEs, 8 architectures, 8 metrics (unlearning, disentanglement, probing, sparse-probing, SCR, TPP, autointerp, absorption). Headline: **proxy metrics do not predict downstream utility.** Matryoshka SAEs underperform on proxies but win on disentanglement at scale — proxies are actively misleading.
- **CE-Bench** (arXiv:2509.00691) — contrastive evaluation.
- **SynthSAEBench** — synthetic ground-truth features.
- **Feature sensitivity audits** (Tian 2025) as a new dimension.
- **Intervention faithfulness**: does ablating/clamping a feature produce the predicted behavioural change? Sparse Feature Circuits and Anthropic's attribution-graph work both push this.

### 4. Replacements If SAEs Collapse

The post-SAE toolkit is already partially assembled:

- **Transcoders / cross-layer transcoders** (Dunefsky et al., Anthropic 2025). Functionally a transposed SAE that approximates a sublayer rather than its activations — yields cleaner circuits. Likely successor.
- **Attribution patching / EAP** (Syed et al.) — gradient-based circuit discovery; outperforms ACDC at fraction of cost.
- **Distributed Alignment Search (DAS)** (Geiger et al.) — learns a causal subspace via gradient descent. Strong causal grounding, no dictionary illusion.
- **Causal scrubbing, path patching, causal mediation** — older but rigorous causal-graph tooling.
- **Linear/sparse probes** — the embarrassing baseline that keeps winning on downstream tasks.

The most likely consensus position by EoY 2026: SAEs survive as a **discovery tool for unknown concepts** (per arXiv:2506.23845, "Use SAEs to Discover Unknown Concepts, Not to Act on Known Concepts") but **lose their claim as the canonical interpretability primitive**. Transcoders + DAS + probes form the working toolkit.

### 5. Paper Opportunities — Two Concrete Proposals

**Proposal A — "Held-Out Activation Audit: A Contamination Test for SAE Feature Claims" (8–10 weeks, 1 GPU-month)**

Take ~5,000 published, named features from Gemma Scope / Neuronpedia / Anthropic's Scaling Monosemanticity. For each, retrieve the human/auto label and the top activating examples. Construct three audit sets per feature: (i) sensitivity set — paraphrases and same-concept exemplars generated by a strong LM; (ii) specificity set — near-duplicates of activators that *lack* the named concept; (iii) causal set — clamping the feature and measuring behavioural shift on a concept-conditioned generation task. Report the joint distribution of (sensitivity, specificity, causal-faithfulness). Hypothesis: a substantial fraction (>40%) of labeled features pass autointerp but fail at least two of the three audits. This is the SAE analogue of a data-contamination study — cheap, high-impact, and confronts the "named feature" social-proof problem head-on. Differentiator from Tian 2025: adds specificity + causal axes, operates on *already-published* features (named-feature accountability), not freshly trained SAEs.

**Proposal B — "Interp-Bench: Head-to-Head Probing of SAEs vs Transcoders vs DAS vs Linear Probes on a Fixed Causal Task Suite" (10–14 weeks)**

Build a benchmark of ~20 causal tasks with ground-truth intermediate variables: indirect object identification, gendered pronoun resolution, modular arithmetic, induction, country-capital, refusal triggers, code-syntax tracking. For each, score four method families on (i) variable localisation accuracy, (ii) intervention success rate (clamping → predicted output change), (iii) compute cost, (iv) human-effort cost. Include linear probes as the embarrassing baseline. Pre-register predictions. Expected finding: SAEs lose to DAS on causal localisation and to linear probes on detection; transcoders win on circuit-level tasks; no method dominates. The community needs this comparison and has been avoiding it.

### Honest Assessment: Bubble or Healthy?

**Partial bubble, partial science.** Publication volume and infrastructure (Neuronpedia, SAELens, Gemma Scope) outpace evidence of downstream utility. DeepMind's quiet deprioritisation, the sensitivity/consistency/illusion trio of critiques, and SAEBench's proxy-metric finding together mean the strong claim — "SAEs decompose models into the right features" — is **not currently supported**. The weak claim — "SAEs are a useful unsupervised concept-discovery tool with known failure modes" — survives. Expect 2026–2027 to bring a substantial pullback in headline SAE papers, redirection toward transcoders and causal methods, and explicit retraction of "monosemanticity" as the framing. Healthy correction in progress; not collapse.

## Part 2: Deep Interaction — Challenging the Premise

**XY check.** You framed this as "is the SAE program over-claiming?" but the better question is *"what interpretability artifact would actually license deployment-grade safety claims?"* SAEs were never going to do that — they are an unsupervised decomposition with no causal guarantee. The real failure mode is the field accepting feature-naming as evidence of understanding. A more leveraged research bet: **skip the SAE-audit paper and write the causal-faithfulness benchmark (Proposal B)**, because (i) audit papers age quickly as architectures change, (ii) a benchmark with pre-registered predictions creates durable infrastructure and forces the community to commit, (iii) it positions you as a methodology arbiter rather than a critic — strategically dominant. Proposal A is the safer first paper; Proposal B is the higher-EV bet. Recommend B if you have the compute, A as a six-week warm-up if you do not.

## Sources

- [Measuring Sparse Autoencoder Feature Sensitivity (Tian 2025)](https://arxiv.org/abs/2509.23717)
- [SAEBench (Karvonen et al. 2025)](https://arxiv.org/abs/2503.09532)
- [Are Sparse Autoencoders Useful? Sparse Probing Case Study](https://arxiv.org/abs/2502.16681)
- [DeepMind: Negative Results for SAEs on Downstream Tasks](https://deepmindsafetyresearch.medium.com/negative-results-for-sparse-autoencoders-on-downstream-tasks-and-deprioritising-sae-research-6cadcfc125b9)
- [Interpretability Illusions with Sparse Autoencoders](https://arxiv.org/abs/2505.16004)
- [Position: Prioritize Feature Consistency in SAEs](https://arxiv.org/abs/2505.20254)
- [Sanity Checks for SAEs: Do They Beat Random Baselines?](https://arxiv.org/html/2602.14111v1)
- [Use SAEs to Discover Unknown Concepts, Not Act on Known Ones](https://arxiv.org/html/2506.23845v1)
- [JumpReLU SAE (DeepMind)](https://arxiv.org/abs/2407.14435)
- [Gemma Scope 2 Technical Paper (DeepMind, Sep 2025)](https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/gemma-scope-2-helping-the-ai-safety-community-deepen-understanding-of-complex-language-model-behavior/Gemma_Scope_2_Technical_Paper.pdf)
- [Circuit Tracing / Attribution Graphs (Anthropic, Lindsey et al. 2025)](https://transformer-circuits.pub/2025/attribution-graphs/methods.html)
- [The Golden Gate Illusion (2026 critique)](https://medium.com/@bulanramai2558/the-golden-gate-illusion-why-sparse-autoencoders-saes-misunderstand-the-physics-of-ai-8bf6cdc52928)
- [Neuronpedia SAEBench Interface](https://www.neuronpedia.org/sae-bench/info)
- [Awesome SAE paper list](https://github.com/zepingyu0512/awesome-SAE)
