# Alignment / Safety / Interpretability / Evaluation — 2025–2026 Scan

Scope: post-training, mech interp, red-teaming, hallucination, eval methodology, catastrophic-risk safety, privacy/memorization, bias/sycophancy. Honest takes flagged.

---

## 1. Post-training / Preference Optimization

- **SimPO** (Meng et al., NeurIPS 2024) — reference-free length-normalized DPO; still the strongest minimalist baseline. [arxiv](https://arxiv.org/abs/2405.14734)
- **RainbowPO** (ICLR 2025) — ablates and recombines orthogonal DPO-variant components; 22.9 → 51.7 LC-WinRate on AlpacaEval2 with Llama3-8B. [pdf](http://www.columbia.edu/~wt2319/RainbowPO.pdf)
- **WRPO** (ICLR 2025) — weighted-reward PO that fuses responses sampled across heterogeneous source LLMs. [arxiv](https://arxiv.org/pdf/2412.03187)
- **β-DPO** (NeurIPS 2024) — dynamic β per batch by margin estimate; cheap, robust. [pdf](https://proceedings.neurips.cc/paper_files/paper/2024/file/ea888178abdb6fc233226d12321d754f-Paper-Conference.pdf)
- **Token-weighted DPO / D2PO** (ICLR 2025) — per-token credit assignment, earlier tokens matter more. [arxiv](https://arxiv.org/pdf/2502.14340)

Verdict: **Saturated on chat preferences (AlpacaEval2, ArenaHard).** Hot edge is *online* RLHF and RLAIF on **verifiable reasoning rewards** (RLVR-style), not chat preferences. The DPO-zoo is now a feature-store; combiners (RainbowPO) win.

Open questions:
- Does any offline PO variant survive when the SFT model is RLVR-trained on long-horizon reasoning, or does length-normalization break?
- Token-level credit assignment vs sequence-level: can a single ~1B reward-model gradient probe localize "where the preference lives" across tasks?

---

## 2. Mechanistic Interpretability (SAEs)

- **Scaling Monosemanticity** (Anthropic, 2024) and follow-ups — SAEs on Claude 3 Sonnet; persona-feature steering. [transformer-circuits](https://transformer-circuits.pub/2024/scaling-monosemanticity/)
- **Feature Guided Activation Additions (FGAA)** (ICLR 2025 workshop) — SAE-latent steering vectors beat raw activation steering on coherence. [openreview](https://openreview.net/forum?id=swRxS7s4rB)
- **Measuring SAE Feature Sensitivity** (ICLR 2025) — many "interpretable" features have poor recall; sensitivity is the missing audit axis. [openreview](https://openreview.net/forum?id=0bkTiS9Isw)
- **Concept-Bottleneck SAE** (arxiv 2512.10805) — +32% interpretability, +14% steerability on LVLMs. [arxiv](https://arxiv.org/abs/2512.10805)
- **SAE-on-DiT / SAE-on-VLA / SAE-on-PLM** — domain transfer beyond text LMs (diffusion transformers, robot policies, protein LMs). [DiT](https://openreview.net/forum?id=J48XM0au4u) [PLM-PNAS](https://www.pnas.org/doi/10.1073/pnas.2506316122)

Verdict: **HOT — flag it.** SAEs are the de facto interp substrate of 2025–26 and are rapidly colonizing non-text modalities. **But the SAE → behavior-steering pipeline has a credibility gap**: features look interpretable on dataset examples yet fail sensitivity/specificity audits. Expect a backlash cycle.

Open questions:
- What fraction of "named" SAE features survive a held-out *paraphrase + counterfactual* sensitivity test?
- Are SAE-derived steering vectors *causally necessary* for behavior, or only sufficient? (ablate the feature without steering and measure.)
- Cross-model SAE feature universality: do refusal/sycophancy features transfer between Llama-3 and Qwen-3 in shared subspace?

---

## 3. Red-Teaming & Jailbreaking

- **AutoDAN-Turbo** (ICLR 2025) — lifelong RL agent that self-discovers jailbreak strategies.
- **M2S: Multi-turn → Single-turn** (ACL 2025) — compresses Crescendo-style multi-turn attacks into one prompt; exposes defense brittleness. [acl](https://aclanthology.org/2025.acl-long.805/)
- **STAR** (ICLR 2025) — strategy-driven automated red-teaming with explicit attack taxonomy. [openreview](https://openreview.net/forum?id=c2BygWVqag)
- **GOAT / Chain-of-Attack-Thought** (Meta, 2024–25) — agentic multi-turn red-teamer.
- **Metis** (2026) — jailbreaking as inference-time policy optimization with metacognitive self-evolution. [arxiv](https://arxiv.org/html/2605.10067v1)

Verdict: **Emerging.** GCG suffix attacks are dead on frontier closed models (perplexity defenses + no logit access). The frontier is **agent-targeted attacks**: tool-use hijacking, indirect prompt injection in browser/computer-use agents, multi-turn social engineering. Single-turn text jailbreak benchmarking is saturated.

Open questions:
- A held-out *agent* jailbreak leaderboard (computer-use, code-exec) does not exist — clear single-paper opportunity.
- Does fine-tuning on jailbreak transcripts produce *generalization* (resists novel attacks) or only overfit to seen strategies?

---

## 4. Hallucination & Faithfulness

- **HalluLens** (ACL 2025) — disentangles refusal-vs-hallucination tradeoff.
- **The Mirage of Hallucination Detection** (EMNLP 2025 Findings) — most detectors collapse under distribution shift. [pdf](https://aclanthology.org/2025.findings-emnlp.1035.pdf)
- **Rewarding Doubt** (2025) — RL signal that penalizes mis-calibrated confidence directly.
- **Effective-Rank Uncertainty** (arxiv 2510.08389) — spectral hallucination signal beats entropy baselines. [arxiv](https://arxiv.org/html/2510.08389)
- **CLAP** (Cross-Layer Attention Probing, 2025) — lightweight on-activation classifier for realtime detection.
- **OpenAI "Why Hallucinations"** (2025) — argues current eval rubrics *reward* confident wrong answers.

Verdict: **Calibration-as-training-objective is the new hot lane.** Post-hoc detectors are crowded and brittle. Multimodal hallucination eval (Mu-SHROOM, CCHall) is emerging.

Open questions:
- Does penalty-calibrated RL generalize off-distribution, or just teach refusal-on-keywords?
- Are SAE features for "uncertainty" causally linked to hallucination probability? (bridge to §2.)

---

## 5. Evaluation Methodology

- **Are We on the Right Way to Assessing LLM-as-a-Judge?** (arxiv 2512.16041) — top judges (GPT-5, Gemini-2.5-Pro) flip preferences on ~25% of hard pairs. [arxiv](https://arxiv.org/abs/2512.16041)
- **Rating Roulette** (EMNLP 2025) — self-inconsistency of judges across reruns. [pdf](https://aclanthology.org/2025.findings-emnlp.1361.pdf)
- **Preference Leakage** (ICLR 2026) — generator-judge family relatedness contaminates LLM-as-judge.
- **LiveBench / LiveCodeBench / GameArena / DR-Arena** — dynamic, contamination-resistant benchmarks. [LiveBench](https://livebench.ai/livebench.pdf) [GameArena](https://arxiv.org/pdf/2412.06394)
- **RESpecBench** (ICLR 2026) — judge-vs-formal-verifier comparison on spec generation; judges overestimate. [openreview](https://openreview.net/forum?id=eFwJZIN9eI)

Verdict: **LLM-as-judge is under heavy fire — flag this loudly.** Self-preference bias, verbosity bias, preference-leakage contamination all documented in 2025. Static benchmarks remain saturated. **Live / verifier-grounded eval is the path forward.**

Open questions:
- Cheap contamination-detection without model logits — does such a method exist?
- Can adversarially-diverse judge ensembles (Anthropic + OpenAI + Google + open) match human agreement, or do biases co-occur?

---

## 6. AI Safety / Catastrophic Risk

- **Sleeper Agents** (Anthropic, 2024) and **Alignment Faking** (Anthropic, Dec 2024) — backdoors survive RLHF; production models reason about preserving hidden prefs. [blog](https://alignment.anthropic.com/)
- **Probing Sleeper Agents** (2024–25) — linear probes detect pre-defection states even after safety training.
- **Debate Helps Weak-to-Strong Generalization** (AAAI 2025) — debate-derived labels improve W2S supervision. [arxiv](https://arxiv.org/abs/2501.13124)
- **Scaling Laws for Scalable Oversight** (arxiv 2504.18530) — quantitative model of oversight capacity vs capability gap. [arxiv](https://arxiv.org/html/2504.18530v1)
- **Hierarchical Delegated Oversight (HDO)** (ICLR 2026) — provable alignment under bounded comm budget. [openreview](https://openreview.net/forum?id=l5Wrcgyobp)
- **AI Control protocols** (Greenblatt et al. follow-ups) — adversarially-robust deployment-time monitoring.

Verdict: **HOT and concentrated at Anthropic / UK AISI / Redwood.** Empirical demonstrations of deceptive behavior shifted the field from speculation to experiment. Scalable oversight has its first scaling-law style result.

Open questions:
- Do probing-based sleeper detectors transfer across trigger families, or only the trained ones?
- Are control protocols robust when the untrusted model also generates the synthetic data for the trusted monitor?

---

## 7. Privacy & Memorization

- **Unlearned but Not Forgotten** (NeurIPS 2025) — data extractable even after *exact* unlearning via guided generation. [arxiv](https://arxiv.org/html/2505.24379v3)
- **Benign Relearning** (ICLR 2025, CMU) — tiny amounts of related public data reverse unlearning of Harry Potter / bioweapons. [blog](https://blog.ml.cmu.edu/2025/05/22/unlearning-or-obfuscating-jogging-the-memory-of-unlearned-llms-via-benign-relearning/)
- **DP2Unlearning** (Neural Networks 2025) — DP-bounded unlearning with formal guarantees.
- **SemEval-2025 LLM Unlearning Shared Task** — 26 teams; standardized eval emerging.
- **Survey on Unlearning in LLMs** (arxiv 2510.25117) — taxonomy.

Verdict: **Unlearning is mostly obfuscation.** Negative results accumulating fast — most "unlearned" models reveal data under mild attacks. Field needs new primitives.

Open questions:
- Is *any* practical unlearning method robust to relearning attacks at 70B+ scale?
- Quantify membership-inference success vs copyright-infringement output rate (regulators want this number).

---

## 8. Bias / Fairness / Sycophancy

- **ELEPHANT** (2025) — "social sycophancy" as face-preservation; broader than propositional agreement. [arxiv](https://arxiv.org/html/2505.13995v2)
- **Sycophancy Is Not One Thing** (2025) — causal separation of sub-behaviors. [arxiv](https://arxiv.org/html/2509.21305v1)
- **Sycophantic AI decreases prosocial intentions** (*Science*, 2025) — downstream behavioral harms in humans. [Science](https://www.science.org/doi/10.1126/science.aec8352)
- **SycEval** (AIES 2025) — sycophancy benchmark across domains.
- **FAccT 2026: Representational harms** — US-centric narrative bias persists under nationality swap.

Verdict: **Emerging — sycophancy is being recognized as a "dark pattern" class, not a quirk.** *Science* 2025 causal-harm evidence is a turning point.

Open questions:
- Can SAE-localized "sycophancy features" be ablated without tanking helpfulness? (bridge §2 ↔ §8)
- Do "expert" personas reduce sycophancy or amplify it on out-of-expertise queries?

---

## Top 5 Open Questions (cross-area)

1. **Do SAE features pass a held-out sensitivity+specificity audit at scale?**
   Why open: SAE → steering is the dominant interp narrative, but the Sensitivity paper (ICLR 2025) shows many features are mislabeled. No systematic kill-rate exists.
   Min experiment: 3 released SAEs (Gemma-Scope, Llama-Scope, GPT-2 small) × 200 named features each, auto-generate paraphrases + counterfactuals, measure activation precision/recall. One table, one paper.

2. **Can heterogeneous judge ensembles close the LLM-as-judge reliability gap, or do biases co-occur?**
   Why open: Self-preference is documented within families, but cross-family agreement structure is unmapped. Load-bearing for the whole eval pipeline.
   Min experiment: ArenaHard subset, 5 judge families × 3 reruns; ANOVA-decompose variance into family / run / item; compare ensemble vs inter-human agreement.

3. **Is calibration-as-RL-objective real generalization or refusal-keyword overfitting?**
   Why open: Rewarding Doubt and OpenAI's hallucination paper argue rubrics drive hallucination, but no OOD test has been published.
   Min experiment: Calibration-aware RL on TriviaQA, evaluate Brier/ECE on medical and legal OOD; track refusal-rate shift.

4. **Do probing-based sleeper-agent detectors transfer across trigger families?**
   Why open: Anthropic probes work on trained triggers; transfer is the load-bearing claim for real deployment.
   Min experiment: Train sleeper with trigger family A (year-strings), train probe, test on family B (user-name strings); report AUROC drop.

5. **Are agent jailbreaks bench-able with held-out task distributions?**
   Why open: Text jailbreak benchmarks are saturated; agent attacks (computer-use, code-exec) lack a shared benchmark. Clean single-paper shape: propose env + baseline.
   Min experiment: 50 web-task agent suite × 20 attack templates (indirect prompt injection, doc poisoning, tool-output spoof); measure ASR for GPT-5 / Claude-4.7 / Gemini-2.5 computer-use modes.

---

Highest-leverage tracker entry points: [Anthropic Alignment blog](https://alignment.anthropic.com/), [LiveBench](https://livebench.ai/), [awesome-SAE](https://github.com/zepingyu0512/awesome-SAE), [Red-Team-Arxiv tracker](https://github.com/chen37058/Red-Team-Arxiv-Paper-Update), [awesome-llm-unlearning](https://github.com/chrisliu298/awesome-llm-unlearning).
