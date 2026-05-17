# Deep Dive 13: Long-Context Reasoning Evaluation Beyond NIAH

## 1. State of the benchmarks (2024–2026)

**NIAH (Needle-in-a-Haystack, Kamradt 2023).** Fully saturated. Every frontier model gets ~100% out to advertised context. HELMET authors show NIAH does not predict downstream long-context performance ([Yen et al., ICLR 2025](https://arxiv.org/abs/2410.02694)).

**RULER (NVIDIA, COLM 2024).** 13 synthetic tasks across retrieval, multi-hop tracing, aggregation, QA. Initially differentiated models, but by 2025 frontier models cluster near ceiling on most subtasks; NVIDIA released [RULER v2](https://openreview.net/pdf?id=ZU9tRffRSA) with multi-key NIAH, multi-value NIAH, and multi-doc QA to restore headroom. Practical takeaway: real "effective context" is ~50–65% of advertised window ([NVIDIA/RULER](https://github.com/NVIDIA/RULER)).

**LongBench v1 (THUDM, ACL 2024)** and **v2 ([Bai et al., 2024](https://arxiv.org/abs/2412.15204)).** v2 is the current standard for realistic multitask long-context QA (8K–2M tokens, 503 MC items, six categories incl. code-repo and structured data). Human experts hit only 53.7% under time pressure. As of mid-2026 top models cluster within ~2 points (Claude Opus 4.5 ~64.4%, Qwen3.5 397B 63.2%): approaching saturation but still discriminative ([LongBench v2 leaderboard](https://longbench2.github.io/)).

**∞Bench / InfiniteBench (OpenBMB, [arXiv 2402.13718](https://github.com/OpenBMB/InfiniteBench)).** 12 tasks at 100K+. Synthetic tasks saturated; novel-summarization and code-debug remain hard.

**LooGLE (2024).** ~21K avg length; long-dependency QA still unsolved but length is now small relative to frontier windows — partly obsolete.

**BABILong ([Kuratov et al., NeurIPS 2024](https://arxiv.org/abs/2406.10149)).** Embeds bAbI reasoning tasks into haystacks up to 1M (10M sample split). The most honest result in the field: models effectively use only 10–20% of context once reasoning is required; even GPT-4-128K degrades past ~13K. Not saturated.

**LV-Eval ([Yuan et al., 2024](https://arxiv.org/abs/2402.05136)).** 5 length levels to 256K with confusing-fact insertion and keyword replacement to defeat memorization. Still discriminative; underused.

**NoCha ([Karpinska et al., EMNLP 2024](https://arxiv.org/abs/2406.16264)).** True/false claim pairs over 67 recently-published novels. Open-weight models at random chance; GPT-4o tops out at 55.8% — the hardest narrative long-context benchmark in print and very much not saturated. Closed dataset to limit leakage.

**HELMET ([Yen et al., ICLR 2025](https://arxiv.org/abs/2410.02694)).** Seven application-centric categories up to 128K, model-based scoring, few-shot for base models. Evaluated 59 LCLMs; categories are mutually low-correlated and NIAH does not predict any of them. Companion **LongProc** targets long-output procedural tasks. Currently the best holistic suite.

**RepoBench ([Liu et al., ICLR 2024](https://arxiv.org/abs/2306.03091))** + **RepoQA (2024)** + **ExecRepoBench (2025).** Repo-scale code completion/QA. RepoBench-P (pipeline) remains hard but is largely retrieval-bottlenecked; no benchmark cleanly isolates "reasoning over the whole repo" from "retrieve then complete."

**Stanford HELM Long Context (Sept 2025).** Meta-suite stitching HELMET, RULER, LongBench v2 with consistent decoding/eval ([crfm.stanford.edu](https://crfm.stanford.edu/2025/09/29/helm-long-context.html)). Useful for honest cross-model comparison.

**Honest saturation summary.** Saturated/near-saturated: NIAH, RULER v1, ∞Bench synthetic, LooGLE. Approaching saturation: LongBench v2, RULER v2 retrieval slices. Not saturated: BABILong (reasoning depth), NoCha (narrative global reasoning), LV-Eval (with distractors), HELMET full-context-reasoning categories, repo-scale code beyond completion.

## 2. Real reasoning over long context

The empirical pattern across BABILong, NoCha, HELMET, and Ref-Long is consistent: **retrieval scales with context; reasoning collapses well before the window limit.** BABILong shows degradation begins at ~10% of advertised context once you need multi-fact chaining; NoCha shows that even sentence-level retrieval works while global narrative reasoning fails ([Karpinska 2024](https://aclanthology.org/2024.emnlp-main.948.pdf)). Ref-Long reports a >60-point human–LLM gap on reference attribution. RAG plateaus near 60% on single-fact QA regardless of context length — suggesting parametric reasoning, not retrieval, is the bottleneck.

## 3. Position bias revisited

Liu et al.'s original **"Lost in the Middle"** ([TACL 2024](https://aclanthology.org/2024.tacl-1.9/)) U-curve persists at 128K+. The 2025 MIT analysis ([techxplore](https://techxplore.com/news/2025-06-lost-middle-llm-architecture-ai.html)) gives a graph-theoretic account tying the U-curve to causal masking compounded over depth; **"Found in the Middle"** ([Hsieh et al., 2024](https://arxiv.org/abs/2406.16008)) shows you can calibrate it out at decode time. Distractor-heavy LV-Eval and RULER multi-hop expose a related failure: models pick lexically-similar distractors over correct evidence at long range, and the bias worsens monotonically with distractor count.

## 4. Long-CoT and long-context: additive or interfering?

Mixed evidence. Databricks' RAG study finds o1 dominates Gemini and Claude up to 128K ([blog](https://www.databricks.com/blog/long-context-rag-capabilities-openai-o1-and-google-gemini)), suggesting reasoning helps. But two caveats: (i) o1 consumes reasoning tokens against the budget — long inputs + long CoT can silently truncate, returning empty completions; (ii) HELMET reports reasoning models gain on full-context-reasoning categories but **lose** on instruction-following-at-length, suggesting interference. BABILong remains hard for reasoning models, indicating long-CoT does not rescue the 10–20% effective-utilization ceiling. Net: weakly additive on retrieval-flavored tasks, near-orthogonal on global reasoning, occasionally interfering on instruction-following.

## 5. Paper proposals

**Proposal A — ADVERSARIAL-LONG: distractor-saturated multi-hop benchmark with controlled position and lexical overlap.** Extend LV-Eval's confusing-fact methodology: for each 2–4 hop question, generate (i) N lexically-similar distractors, (ii) N semantically-similar distractors, (iii) controlled placement (start/middle/end of evidence chain). Factorial design over {hops, distractor-type, position, length∈[32K, 1M]}. Report not just accuracy but a **fragility curve**: accuracy drop per added distractor. Hypothesis: fragility slope is the discriminative signal frontier benchmarks lack. Anchors on Ref-Long's human–LLM gap and BABILong's reasoning depth.

**Proposal B — REPOREASON: repo-scale reasoning isolated from retrieval.** Existing repo benchmarks conflate retrieval and completion. Construction: take real PRs from large monorepos; for each, manually identify the minimum cross-file evidence set, then ship the model the **full repo** and ask reasoning questions ("which call sites break if function F changes signature?", "find the bug given this failing test"). Two conditions: full repo (≥200K tokens) vs. oracle-retrieved minimum set. The difference quantifies reasoning loss attributable to context dilution, not retrieval failure. Pairs naturally with our experiment v3 SWE-bench diagnostic study.

**Optional C — long-CoT × long-context interaction matrix.** 2×2 design (reasoning on/off × context short/long) across HELMET categories, measuring additive vs. interference. Smaller scope, high-signal negative-result paper.

## Bottom line

NIAH and RULER v1 are dead for differentiation. LongBench v2 has ~12 months left. The honest frontier is BABILong, NoCha, HELMET full-reasoning slices, and LV-Eval with distractors — all converging on the same story: **retrieval scales, reasoning doesn't.** That gap is the paper opportunity.
