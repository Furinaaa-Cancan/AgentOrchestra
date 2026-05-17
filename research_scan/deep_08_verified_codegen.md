# Deep-Dive 08: Verified Code Generation × Reasoning Models

Scope: formal-verification-grade codegen (Lean / Dafny / Coq / F* / Verus) under modern reasoning LLMs (o1, R1, DeepSeek-Prover-V2). Cross-formalism transfer is the headline question.

## 1. State of the Art 2024–2026 (formal math)

The Lean side is saturating fast.

- **AlphaProof / AlphaGeometry-2** (Google DeepMind, Nature 2025). AlphaZero-style RL over auto-formalized problems; IMO 2024 silver-medal. Published Oct 2025: <https://www.nature.com/articles/s41586-025-09833-y>.
- **DeepSeek-Prover-V2** (671B, April 2025): 88.9% miniF2F-test, 49/658 PutnamBench. <https://arxiv.org/abs/2504.21801>.
- **HILBERT** (2025): 99.2% miniF2F, 462/660 PutnamBench (70.0%), beating proprietary SeedProver (50.4%). <https://arxiv.org/pdf/2509.22819>.
- **Lean-STaR**: bootstrapped reasoning-trace SFT for Lean tactics — now a baseline in nearly every recent paper.
- **miniF2F-Lean Revisited** (Nov 2025): argues miniF2F is contaminated/saturated and proposes harder splits. <https://arxiv.org/pdf/2511.03108>.

Takeaway: miniF2F is dead as a discriminator. PutnamBench is the live frontier; CombiBench and FormalMATH are the new harder targets (<https://arxiv.org/html/2505.03171>, <https://arxiv.org/pdf/2505.02735>).

## 2. Dafny / F* / Verus / Frama-C

Much smaller community, but real momentum.

- **Clover** (Stanford, Sun et al., AIV 2024): closed-loop consistency among code, docstring, Dafny annotations. CloverBench: ~87% acceptance on correct programs, 0 false positives. <https://arxiv.org/abs/2310.17807>, blog <http://ai.stanford.edu/blog/clover/>.
- **Dafny as Verification-Aware Intermediate Language** (Jan 2025): proposes Dafny as the IL between LLM and target language. <https://arxiv.org/pdf/2501.06283>.
- **DafnyBench** (2025): aggregates Clover + DafnySynthesis + GitHub scrapes.
- **AutoVerus** (Microsoft, OOPSLA/PACMPL 2025): multi-agent LLM pipeline for Verus/Rust proofs; >90% solve rate on their benchmark, often <30s. <https://arxiv.org/abs/2409.13082>, <https://dl.acm.org/doi/10.1145/3763174>.
- **SAFE** (Microsoft, ICLR 2025): self-evolving fine-tuned LLM for Verus, 9,706 verified programs synthesized. <https://www.microsoft.com/en-us/research/wp-content/uploads/2024/10/ICLR_25_SelfEvolveAutoVerus.pdf>.
- **AlphaVerus** (CMU/MSR, Parno et al.): bootstrapping verified codegen end-to-end. <http://www.contrib.andrew.cmu.edu/~bparno/papers/alpha-verus.pdf>.
- **KVerus** (2026): retrieval-augmented, self-adaptive Verus proof generation from system specs. <https://arxiv.org/html/2605.03822v1>.
- **Frama-C + LLM**: essentially nothing major. ACSL annotation generation lives in workshop papers; no flagship.

## 3. Cross-formalism transfer — the actual void

Three relevant works exist; none is a clean transfer study.

- **ProofWala** (Feb 2025): multilingual proof-step model trained on Lean + Coq. Reports modest mutual improvement when training on both vs. one. <https://arxiv.org/pdf/2502.04671>. This is the closest existing transfer paper, but it is Lean↔Coq (both ITPs) — not the auto-active jump to Dafny/Verus.
- **miniF2F-Dafny** (Dec 2025): first port of miniF2F into Dafny via auto-active verification — enables comparing Lean vs. Dafny on identical math. <https://arxiv.org/html/2512.10187v1>.
- **Vericoding benchmark** (Sept 2025): translates tasks across Dafny / Verus / Lean3 using an LLM translator. <https://arxiv.org/pdf/2509.22908>.
- **CLEVER** (May 2025): curated formally verified codegen benchmark. <https://arxiv.org/pdf/2505.13938>.

What is missing: a controlled study that trains/SFTs on Lean tactic traces and *measures* zero-shot Dafny/Verus performance (or vice versa), separating shared-reasoning skill from per-prover syntax. ProofWala hints, miniF2F-Dafny enables it, nobody has done it.

## 4. Industrial reality

- **AWS s2n-tls**: Galois SAW/Cryptol equivalence proofs, in CI for years (<https://aws.amazon.com/blogs/security/automated-reasoning-and-amazon-s2n/>). Human-written, LLMs not involved.
- **AWS Provable Security** (IAM Zelkova, S3 Tiros): SMT, not LLM.
- **Microsoft**: AutoVerus / SAFE are research, not shipped in Windows/Azure. ImageGen of proofs is not a product.
- **DeepMind**: AlphaProof is internal research.
- **Startups**: Atlas Computing (<https://atlascomputing.org/ai-assisted-fv-toolchain.pdf>) is the most visible "AI + FV" outfit; still pre-product.

Bottom line: zero shipping verified-codegen products. Industrial FV exists but uses classical tools. This is a gap, not a market.

## 5. Benchmark landscape

| Benchmark | Formalism | Status |
|---|---|---|
| miniF2F | Lean / Isabelle / HOL Light | saturated |
| PutnamBench | Lean / Coq / Isabelle | live frontier |
| FormalMATH, CombiBench | Lean | new, harder |
| CloverBench, DafnyBench | Dafny | small, textbook-level |
| Verus-bench (AutoVerus) | Verus/Rust | ~150 tasks |
| Vericoding | Dafny+Verus+Lean3 | only cross-formalism bench |
| CLEVER | Lean (codegen-flavored) | new |

Real gap: no large, **adversarially curated**, cross-formalism verified-codegen benchmark with real-world specs (not textbook arithmetic). Vericoding is the closest precursor.

## 6. Paper proposals

**Proposal A — "Does formal reasoning transfer? A controlled Lean→Dafny→Verus study."**
Take a reasoning-tuned base (DeepSeek-Prover-V2 or R1-distill-Lean), SFT only on Lean tactic traces, then zero-shot + few-shot evaluate on miniF2F-Dafny, DafnyBench, and AutoVerus tasks. Mirror: SFT on Verus, evaluate on Lean. Ablate: (i) shared latent reasoning vs. (ii) syntactic token overlap vs. (iii) verifier-feedback loop. Deliverable: a transfer matrix + a clean answer to "is verified codegen one skill or N skills?" Modest compute (~few thousand GPU-hours). Target: ICLR / NeurIPS D&B / ICML. Plausibility of acceptance: solid — the question is well-posed, infrastructure (miniF2F-Dafny, Vericoding) just landed, and reviewers like negative-or-surprising transfer findings.

**Proposal B — "VeriReason-Bench: a reasoning-model benchmark for auto-active verification."**
Build a ~500-task benchmark spanning Dafny + Verus + F*, drawn from (a) real CVE-relevant snippets (parsers, crypto primitives, allocators), (b) competitive programming with verified post-conditions, (c) adversarial near-miss specs to catch spec-gaming. Evaluate o1, o3, R1, Claude 4.7, DeepSeek-Prover-V2, AutoVerus pipeline, Clover loop. Report not only solve rate but **specification-faithfulness** (does the LLM weaken the spec to pass?) — a measurement nobody has standardized. Target: NeurIPS D&B. Acceptance plausibility: high if the spec-gaming axis is genuinely novel and the tasks have provenance beyond textbook.

## 7. Honest verdict — niche or hot?

Lean theorem proving is **hot but crowded** (DeepMind, DeepSeek, Bytedance/SeedProver, every Chinese lab). Marginal contribution is hard.

Dafny / Verus / F* with LLMs is **warm and uncrowded**. Microsoft owns Verus, Stanford+Amazon poke at Dafny, almost nobody touches F*/Frama-C. A well-executed cross-formalism transfer paper (Proposal A) is a NeurIPS/ICLR-tier contribution because: (a) infra finally exists in 2026, (b) the result either way is interesting (transfer works → unifies the field; transfer fails → motivates per-prover training), (c) reasoning-model angle is current.

Risk: reviewers from the Lean-math camp may consider Dafny "not real verification," while PL reviewers may consider it "not real ML." Pick venue accordingly — ICLR is friendlier than POPL/PLDI; NeurIPS D&B safest for the benchmark. Avoid CAV/POPL unless co-authoring with an FV insider.

Net: this is **a genuine paper opportunity, not too niche** — but only if you commit to cross-formalism scope. A "yet another Lean prover" paper is dead on arrival in 2026.
