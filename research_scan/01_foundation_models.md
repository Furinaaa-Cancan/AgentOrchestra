# Foundation Models / Architecture / Pretraining — Landscape Scan (2025–2026)

Scope: architecture, MoE, scaling/data, pretraining innovations, long context, specialized base models. Excludes reasoning/agents, alignment, applications, efficiency-as-end (covered by sibling agents).

---

## 1. Architecture Beyond Transformer

Representative papers:
- **Mamba: Linear-Time Sequence Modeling with Selective State Spaces** (Gu & Dao, ICLR 2024 oral, still the reference). Selective SSM with hardware-aware scan. https://arxiv.org/abs/2312.00752
- **Hybrid Transformer-Mamba Language Models (Jamba family)** — ICLR 2025. 43% SSM + 7% attention beats pure transformer at long-context throughput. https://proceedings.iclr.cc/paper_files/paper/2025/file/a9ed43fa31dc8b4a7d7a673d713dcb5f-Paper-Conference.pdf
- **"Achilles' Heel of Mamba"** — NeurIPS 2025 spotlight. Mamba systematically fails on copy/recall tasks; clean negative result that motivates hybrids.
- **RWKV-7 "Goose" with Expressive Dynamic State Evolution** (Mar 2025). Generalized delta rule, vector-valued gating, in-context learning rate. https://openreview.net/forum?id=ayB1PACN5j
- **Gated Attention** — NeurIPS 2025 Best Paper. Sigmoid gate per head removes attention sinks, improves training stability.
- **LLaDA: Large Language Diffusion Models** (Nie et al., 2025). 8B masked-diffusion LM competitive with LLaMA3-8B; breaks reversal curse. https://arxiv.org/abs/2502.09992

Verdict: **Pure SSM is saturated/cooling** (Achilles-heel results killed the "replace transformer" narrative). **Hybrids are hot** (Jamba, RWKV-X, Zamba-style). **Diffusion LLMs are emerging** — LLaDA proved viability at 8B; Gemini Diffusion productized it.

Open questions:
- What is the minimum attention budget in a hybrid that preserves all in-context-learning capabilities? Existing ratios (7–25%) are folklore, not principled.
- Do diffusion LLMs scale by Chinchilla-like laws, or do they have a fundamentally different compute-optimal frontier? No scaling-law paper exists for masked-diffusion LMs above 8B.
- Can you train a hybrid whose attention layers are learned-sparse over a structural prior (induction-head positions) rather than fixed-stride?

---

## 2. Mixture of Experts

Representative papers:
- **DeepSeek-V3 Technical Report** (Dec 2024). 671B/37B-active, 256 fine-grained experts, auxiliary-loss-free load balancing, Multi-head Latent Attention. The de facto reference recipe.
- **Joint MoE Scaling Laws: Mixture of Experts Can Be Memory Efficient** (Feb 2025). https://arxiv.org/pdf/2502.05172
- **MoE++** — ICLR 2025. Adds "zero/copy/constant" null experts to accelerate routing. https://proceedings.iclr.cc/paper_files/paper/2025/file/7efe88bb4138d602e56637cfcf713654-Paper-Conference.pdf
- **Mixture Compressor for MoE LLMs** — ICLR 2025. Post-training expert pruning + quantization.
- **Towards a Comprehensive Scaling Law of MoE** (Sep 2025). https://arxiv.org/html/2509.23678v1

Verdict: **Fine-grained + shared-expert + aux-loss-free is the consensus stack — saturated as engineering**. **Hot**: scaling laws that jointly optimize sparsity × parameter × token budgets; **emerging**: MoE for non-LLM modalities and MoE distillation.

Open questions:
- Does *expert specialization* arise from routing, or is it imposed by the loss? Causal ablation (force-random routing during early pretraining, then unlock) is missing.
- Optimal active-fraction as a function of data quality: at fixed FLOPs, does cleaner data favor denser or sparser models? Unstudied.
- Can experts be merged post-hoc with no loss using SLERP-like geodesic averaging — and if so, what does that say about routing entropy?

---

## 3. Scaling Laws & Data

Representative papers:
- **Scaling Data-Constrained Language Models** (Muennighoff et al., updated 2025). Up to 4 epoch-repeats are ~free; beyond that, compute decays. https://arxiv.org/abs/2305.16264
- **Scaling Laws of Synthetic Data for Language Models / SynthLLM** (Mar 2025). https://arxiv.org/abs/2503.19551
- **Scaling Laws for Precision** — ICLR 2025 (Kumar et al.). Low-precision training has its own optimal token/parameter ratio. https://pehlevan.seas.harvard.edu/sites/g/files/omnuum6471/files/2025-03/Kumar_etal_ICLR_2025.pdf
- **Prescriptive Scaling Laws for Data-Constrained Training** (2025 preprint — flagged below: arxiv id looks unusual, verify before citing).

Verdict: **Chinchilla as point estimate is saturated**. **Hot**: data-quality-aware laws, repetition laws, precision-aware laws. **Emerging**: synthetic-data scaling exponents — early evidence that synthetic data has a *lower* asymptote than real data, but the field hasn't agreed on a functional form.

Open questions:
- Is there a *data-quality exponent* — can quality filtering be made a third variable in the Chinchilla equation with a clean empirical fit?
- At what synthetic:real mixing ratio does model collapse begin, and is this ratio a function of generator/student capability gap? No clean phase diagram exists.
- Does the "4-epoch free repetition" result hold at 100B+ scale, or is it a sub-7B artifact?

---

## 4. Pretraining Innovations

Representative papers:
- **Byte Latent Transformer (BLT): Patches Scale Better Than Tokens** — ACL 2025 / ICLR 2025. Entropy-based dynamic patching; first byte-level FLOP-controlled study to 8B/4T bytes. https://arxiv.org/abs/2412.09871
- **EvaByte: Efficient Byte-level Language Models at Scale** (HKU NLP, 2025). https://hkunlp.github.io/blog/2025/evabyte/
- **ICLR: In-Context Learning of Representations** — ICLR 2025. Pretraining structure determines how concepts are organized; can be overridden in-context. https://arxiv.org/abs/2501.00070
- **Curriculum Learning for LLM Pretraining: An Analysis of Learning Dynamics** (Jan 2026 preprint). HMM analysis of data ordering effects.
- **Unified multimodal (BLIP3-o, UniGen, "Emerging Properties in Unified Multimodal Pretraining")** — all May 2025. Mixed-modal early-fusion successors to Chameleon.

Verdict: **Tokenizer-free is emerging hot** — BLT broke the 8B barrier; 2026 will likely see 30B+ byte models. **Curriculum learning is saturated as a method but emerging as a science** (people now study *why* ordering matters via HMM/dynamics, not whether). **Native multimodal early-fusion is hot** — VLM share at top venues jumped from 16% (2023) to 40% (2025).

Open questions:
- Does BLT's entropy-patching converge to morpheme-like units in low-resource languages, and does that explain its robustness? No linguistic analysis exists yet.
- Joint vision+text+audio *from scratch* (no LM init) vs. LM-init multimodal: what is the compute-equivalent loss in language ability? Almost everyone still inits from a text LM.
- Curriculum: is there a measurable "irreversibility" — data seen early but never repeated leaves a different footprint than data interleaved? HMM paper suggests yes; needs causal intervention.

---

## 5. Long Context

Representative papers:
- **YaRN: Efficient Context Window Extension of LLMs** (Peng et al., ICLR 2024; still the baseline). https://arxiv.org/abs/2309.00071
- **LongRoPE2: Near-Lossless LLM Context Window Scaling** (2025). >98.5% short-context accuracy retained at 128K. https://openreview.net/forum?id=jwMjzGpzi4
- **DeepSeek-V3 Multi-head Latent Attention** — low-rank latent KV compression; 128K native.
- **Gemini 1.5/2.5 long-context technical reports** — 1M–2M tokens; Grok-4-fast 2M (2025).

Verdict: **Naive context extension is saturated** — every frontier model claims 1M+. **Hot**: retrieval-augmented pretraining (training with retrieved chunks in-context, not just at inference) and KV compression (MLA, hybrid SSM caches). **Emerging**: faithful long-context *reasoning* — needle-in-haystack is solved, multi-hop over 500K tokens isn't.

Open questions:
- Position-encoding-free architectures (NoPE, SSM-only) at 1M context: do they actually generalize length, or do hybrid models cheat via the attention layers?
- Is there a principled way to choose RoPE base-frequency at pretraining time so *no* post-hoc extension is needed? Current practice (10K → 1M base) is heuristic.
- "Effective context" vs. "advertised context" — a benchmark that measures information-density retention as a function of position would land cleanly; RULER/LongBench are coarse.

---

## 6. Specialized Base Models

Representative papers:
- **DeepSeekMath** (Feb 2024, foundational). Code-LM continued pretraining on 120B math tokens. https://arxiv.org/abs/2402.03300
- **DeepSeek-Math-V2** (2025/2026). RL for proof quality with internal verifier; V3.2-Exp backbone, 128K context.
- **Qwen2.5-Math, Llemma, InternLM-Math** — math-specialized continued-pretraining family.
- **Galactica successors**: no widely accepted scientific base model since 2022. Flagged as a gap, not a citation.

Verdict: **Math + code base models are saturated as a recipe** (code-init → math-corpus → RL-verifier). **Emerging**: domain bases for biology (Evo-2, ESM-3 lineage), chemistry (UniMol-2), theorem proving (with Lean kernel in the loop). **Hot under-served**: scientific generalist — Galactica's failure has not been retried at scale despite vastly improved data filtering.

Open questions:
- Code-init is treated as gospel for math models — is it actually optimal, or sunk-cost convention? A clean ablation (NL-init vs. code-init vs. math-init) at matched compute is missing.
- Is there a "specialist tax" — a measurable degradation in general ability per X tokens of specialized continued pretraining? Practitioners trade this off blind.
- Can a single base model be Pareto-optimal across math + code + bio, or do the domains actively interfere? No three-way clean study.

---

## Top 5 Open Questions

1. **What is the minimum attention budget in a hybrid SSM-attention model that preserves in-context learning?**
   - Why open: Jamba (7%), Zamba, RWKV-X all chose ratios by intuition. Achilles-Heel-of-Mamba showed pure SSM fails copy/recall — but nobody has the threshold curve.
   - Minimal experiment: Train 1.3B hybrid at fixed compute, sweep attention layer fraction in {0, 1/16, 1/8, 1/4, 1/2, 1}. Evaluate on (a) MQAR/needle, (b) MMLU, (c) GSM8K few-shot. Find the inflection point. Clean NeurIPS-shape.

2. **Do diffusion LLMs follow Chinchilla, or a different compute-optimal frontier?**
   - Why open: LLaDA 8B trained on 2.3T tokens vs. LLaMA3's 15T and is comparable. Either LLaDA is on a different (better?) scaling curve, or its training is under-optimized. No paper measures this.
   - Minimal experiment: Train masked-diffusion LMs at 5 (params, tokens) points spanning 200M–3B, fit a Hoffmann-style law, compare to matched AR baselines. ICML/NeurIPS-shape.

3. **Is there a measurable data-quality exponent that extends Chinchilla into 3D (compute × tokens × quality)?**
   - Why open: Everyone says "quality matters" but the law remains 2D. Phi/Cosmopedia work is empirical anecdote; SynthLLM gives synthetic curves but not a unified law.
   - Minimal experiment: Filter Common Crawl at 4 quality tiers (e.g., FineWeb-Edu thresholds). Train Chinchilla-optimal models at each tier across 4 compute scales. Fit L(N, D, Q). Even a negative result is publishable.

4. **At what synthetic:real mixing ratio does model collapse begin, and how does the boundary depend on the generator–student capability gap?**
   - Why open: Shumailov-style collapse work used pure-synthetic recursion. Practical pipelines mix. Phase diagram unknown and matters urgently as 2026 frontier runs lean harder on synthetic.
   - Minimal experiment: Pretrain 350M students on (real fraction r, generator strength G) grid. Measure held-out *real* NLL, n-gram entropy, MMLU. Map the collapse boundary. ACL/EMNLP-shape.

5. **Position-encoding-free long context: do NoPE and SSM-only models truly length-generalize, or do hybrids smuggle in attention's length-extrapolation?**
   - Why open: "Infinite context" claims for RWKV/Mamba are based on perplexity, not retrieval. LongRoPE2 dominates in practice. Honest matched comparison hasn't been done at 1M.
   - Minimal experiment: Train matched ~1B models: (a) RoPE+YaRN, (b) NoPE attention, (c) pure Mamba-2, (d) Jamba-style hybrid. Evaluate on RULER, needle-in-haystack, and a new multi-hop-over-500K benchmark. Ablate the attention layers in the hybrid. ICLR-shape.

---

Honest flags:
- "Prescriptive Scaling Laws for Data-Constrained Training" (arxiv 2605.01640) surfaced in search with an unusual id — treat as preprint, verify before citing.
- "Principled Synthetic Data … Recommendation" (arxiv 2602.07298) likewise — possibly misindexed search hit.
- No widely accepted Galactica successor exists; cited as a gap, not a paper.
- "Curriculum Learning for LLM Pretraining: An Analysis of Learning Dynamics" (arxiv 2601.21698) has an unusual id; verify the canonical version.
