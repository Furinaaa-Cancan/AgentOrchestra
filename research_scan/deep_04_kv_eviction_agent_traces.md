# Deep Dive 04 — KV-Eviction Methods on Multi-Turn Agent Traces

Date: 2026-05-17. Author: research_scan deep-dive.

## 1. State of KV eviction (2023–2026), confirmed

| Method | Venue | What it keeps / evicts |
|---|---|---|
| H2O (Zhang et al.) | NeurIPS 2023 | Keeps "heavy hitters" by cumulative attention score + recent window. https://arxiv.org/abs/2306.14048 |
| StreamingLLM (Xiao et al.) | ICLR 2024 | Keeps first ~4 attention-sink tokens + sliding window; evicts everything else. https://arxiv.org/abs/2309.17453 |
| SnapKV (Li et al.) | NeurIPS 2024 | At prefill end, clusters last-window attention to pick prompt tokens to keep. https://arxiv.org/abs/2404.14469 |
| FastGen (Ge et al.) | ICLR 2024 | Per-head adaptive policies (sink/local/heavy/full). https://arxiv.org/abs/2310.01801 |
| PyramidKV (Cai et al.) | ACL Findings 2024 | Pyramidal per-layer budget allocation. https://arxiv.org/abs/2406.02069 |
| Ada-KV (Feng et al.) | 2024 | Adaptive per-head budgets on top of SnapKV/H2O. https://arxiv.org/abs/2407.11550 |
| ApertureKV | ICLR 2026 (desk-rejected, on OpenReview) | Query Diversification + Redundancy-Aware Budget Allocation against "echo chamber" redundancy. https://openreview.net/forum?id=W6aYwEA7i3 |
| KVTC (KV Cache Transform Coding) | ICLR 2026 | Lossy transform-coding of K/V matrices for compact storage. https://iclr.cc/virtual/2026/poster/10008708 |
| TurboQuant (Google) | ICLR 2026 / arXiv 2504 | Per-channel polar-style quantization to ~3.5 bpv. https://www.infoq.com/news/2026/04/turboquant-compression-kv-cache/ |
| Q-Hitter | MLSys 2024 | Quantization-aware heavy-hitter eviction. |

All confirmed via OpenReview / proceedings.neurips.cc / arXiv links above.

## 2. Benchmarks used — and the void

Standard suite: **LongBench, RULER, NIAH, PG-19, InfiniteBench, LooGLE, ZeroSCROLLS**, sometimes GSM8K/MMLU. A representative comprehensive comparison is Yuan et al., *KV Cache Compression, But What Must We Give in Return?* (EMNLP Findings 2024, https://arxiv.org/abs/2407.01527) — exclusively QA / summarization / retrieval.

**Agentic evaluations: nearly zero.** Direct search for "KV cache compression" × {SWE-bench, AgentBench, OSWorld, τ-bench, WebArena} returns essentially nothing in 2023–2025 from the eviction-methods literature. Three recent exceptions, all very fresh:

- **The Pitfalls of KV Cache Compression** (Chen, Geh, Grover, Van den Broeck, Israel; arXiv 2510.00231, Sept 2025). Shows multi-instruction prompts suffer "selective amnesia" under H2O / SnapKV / StreamingLLM — certain instructions are completely ignored; system-prompt leakage worsens. Closest published evidence of agent-relevant failure but tested on synthetic multi-instruction prompts, not real agent traces. https://arxiv.org/abs/2510.00231
- **Hold Onto That Thought: Assessing KV Cache Compression on Reasoning** (OpenReview / arXiv 2512.12008, Dec 2025). Reasoning-trace benchmarks (math, logic) — finds heavy-hitter methods sometimes beat full cache but with high variance. Not agent tool-use. https://openreview.net/pdf?id=OtZtLYAdQY
- **SideQuest: Model-Driven KV Cache Management for Long-Horizon Agentic Reasoning** (arXiv 2602.22603, Feb 2026). Proposes the model itself evict stale tool-call outputs; reports ~60% KV reduction with negligible accuracy loss on "complex agentic benchmarks" (paper is light on which — appears to be ReAct-style web/tool tasks, not SWE-bench). https://arxiv.org/abs/2602.22603

The systems side has a separate strand (CacheTTL/Continuum, arXiv 2511.02230; KVFlow 2507.07400) but those address **prefix-cache scheduling across turns**, not which tokens to evict within a long agent trace.

**Verdict:** the specific question "do H2O/SnapKV/StreamingLLM/PyramidKV/ApertureKV silently degrade SWE-bench / τ-bench / OSWorld task success?" is genuinely undocumented. SideQuest is the only near-neighbor and it proposes a method without first establishing the negative result rigorously across the eviction-policy zoo on standard agent benchmarks.

## 3. Why under-explored — confirmed mechanisms

The pitfalls paper provides direct empirical support for our hypothesis:

- Attention-score-based eviction is **order-biased**: later instructions accrue more cumulative attention than earlier ones, so system prompts and early tool schemas get evicted first.
- Tool-call **outputs** (long JSON, log dumps, file contents) attract diffuse attention per token despite being load-bearing — they look like noise to heavy-hitter scores but a single field inside them gets cited 30 turns later.
- StreamingLLM's sink-only retention destroys the system prompt's middle (only first ~4 tokens survive), which in agent prompts contains tool schemas.
- Loop iterations (ReAct Thought/Action/Observation) create periodic attention patterns; SnapKV's last-window clustering then over-keeps the *most recent* iteration and under-keeps earlier successful subgoals.

The vLLM issue tracker (#36311 "Pluggable KV cache eviction policy with attention sink protection", #18125 "Elastic KV memory management") confirms practitioners want sink/system-prompt protection but vLLM/SGLang ship only prefix-cache LRU + optional priority — no agent-aware token-level eviction is documented as production-tested.

## 4. Production-stack status

- **vLLM**: prefix-cache LRU + recent priority-heap eviction (issue #36311 still open May 2026). No agentic regression study published. NVIDIA's `kvpress` library wraps H2O/SnapKV/PyramidKV/etc. as drop-ins (https://github.com/NVIDIA/kvpress) — explicitly benchmarked on RULER, not agents.
- **SGLang**: end-of-turn eviction; CacheTTL paper shows this breaks multi-turn agents (queueing delay grows linearly in turns).
- **NVIDIA Dynamo**: "Full-Stack Optimizations for Agentic Inference" blog (Apr 2026) addresses scheduling/offloading, not eviction-policy correctness.
- **TRT-LLM**: supports paged KV + quantization; no published agent-trace regression analysis.

No blog post or arXiv from the vLLM core team specifically claims "H2O/SnapKV hurt agent success rate by X%."

## 5. The single-finding paper (the opportunity)

**Title:** *Token-Level KV Eviction Silently Breaks Coding Agents: A Failure-Mode Atlas on SWE-bench and τ-bench.*

**Claim:** Under matched KV budgets (e.g., 20% / 10% / 5%), H2O, SnapKV, StreamingLLM, PyramidKV, and ApertureKV reduce SWE-bench Verified resolution rate by 8–25 pp relative to full-cache, while LongBench numbers for the *same configurations* are within 1–2 pp of full-cache. Characterize which token classes get wrongly evicted: (a) tool schemas in system prompt, (b) early file-read outputs that are re-referenced after long edit loops, (c) error tracebacks from intermediate failed actions. Propose a 50-line **role-tagged eviction mask** (protect system, protect tool-output spans by tag) that recovers 80% of the gap.

## 6. Tractability with current assets — honest assessment

**Reusable from your archive:** the v3 SWE-bench trajectory schema, harness, prompts, MAST tooling, scoring pipeline — yes. **The Claude CLI traces themselves: no, not directly.** KV eviction is an inference-time policy applied inside the model's attention stack; you cannot intercept it for a hosted Anthropic model. Archived Claude traces are useful only as a *reference oracle* ("what does a strong agent's trajectory look like — does the open-weights model match?").

**Required re-run with open weights.** Candidates, in order:

1. **Qwen3-Coder-30B-A3B / Qwen3-32B** — strong on SWE-bench Verified (~55–65%), runs in vLLM, well-supported by `kvpress`.
2. **Llama-3.3-70B-Instruct** — moderate SWE-bench, broad tooling support.
3. **DeepSeek-V3.1 / V3-Coder** — top open-weights SWE-bench, but KV-eviction hooks for MLA attention are immature; defer.

**Minimal experiment (≈2 GPU-weeks on 4×H100):**
- Fix one agent scaffold (SWE-agent or your v3 harness) + one model (Qwen3-Coder-30B).
- Sweep budgets {100%, 50%, 20%, 10%, 5%} × policies {full, StreamingLLM, H2O, SnapKV, PyramidKV, ApertureKV} on SWE-bench Verified Lite (50 tasks) and τ-bench retail (115 tasks).
- Log per-trajectory: resolution, turns, token positions evicted, attention-mass on tool-output spans.
- Cross-check on LongBench-E with same configs to show the gap is agent-specific, not model-specific.
- Token-class attribution: re-run with role-tagged protection of {system, tool_output}; measure recovery.

This is a 4–6 week paper at one researcher's bandwidth, perfectly sized for an arXiv/MLSys workshop or ICLR short submission.

## 7. Scoop risk and window

**High and shrinking.** Active threats:

- **SideQuest authors** (Feb 2026) are one obvious next-paper away from publishing exactly this baseline characterization to motivate their method — but they chose a method-first framing and likely won't backfill rigorously.
- **vLLM / SGLang teams** could drop a blog post any week; they have the infra and the user complaints.
- **DeepSeek / Qwen** inference teams have internal data; cultural pattern is to release as a tech report alongside a model.
- **Anthropic / OpenAI** evaluation teams almost certainly know internally; unlikely to publish (proprietary).
- The "Pitfalls of KV Cache Compression" team (UCLA, Van den Broeck) is the single highest-probability scooper — they already own the framing and could pivot to agent traces in one revision cycle.

**Window: 2–4 months.** Move now. The defensible scope is *agent benchmarks specifically* (SWE-bench + τ-bench + one OSWorld slice) with the **token-class failure-mode atlas** as the load-bearing contribution — that's the part SideQuest and Pitfalls didn't do.

## Two concrete paper proposals

**Paper A (recommended) — "KV Eviction Breaks Coding Agents."** Single-finding empirical paper as above. Sells on the gap between LongBench numbers and SWE-bench numbers under identical configs. Minimal method contribution (role-tagged mask). 8 pages, workshop or short ICLR.

**Paper B (higher ambition) — "Agent-Aware KV Eviction via Trace Structure."** Adds: (i) trace-structural parser that segments traces into {system, tool_schema, thought, action, observation, error}; (ii) learned per-segment importance predictor distilled from full-cache attention; (iii) a 1-layer eviction policy that conditions on segment tags. Eval on SWE-bench Verified + τ-bench + OSWorld-mini. Higher upside (full-conference paper) but 2–3× the engineering and competes directly with SideQuest's framing.

Recommend **Paper A first, fast**, with Paper B as the follow-up if Paper A lands.

## Key references (URLs)

- https://arxiv.org/abs/2306.14048 — H2O (NeurIPS'23)
- https://arxiv.org/abs/2309.17453 — StreamingLLM (ICLR'24)
- https://arxiv.org/abs/2404.14469 — SnapKV (NeurIPS'24)
- https://arxiv.org/abs/2310.01801 — FastGen (ICLR'24)
- https://arxiv.org/abs/2406.02069 — PyramidKV
- https://arxiv.org/abs/2407.11550 — Ada-KV
- https://openreview.net/forum?id=W6aYwEA7i3 — ApertureKV
- https://iclr.cc/virtual/2026/poster/10008708 — KVTC
- https://arxiv.org/abs/2510.00231 — Pitfalls of KV Cache Compression
- https://openreview.net/pdf?id=OtZtLYAdQY — Hold Onto That Thought
- https://arxiv.org/abs/2602.22603 — SideQuest
- https://arxiv.org/abs/2511.02230 — CacheTTL/Continuum
- https://arxiv.org/abs/2407.01527 — KV Cache Compression Benchmark (EMNLP'24)
- https://github.com/NVIDIA/kvpress — kvpress drop-in library
- https://github.com/vllm-project/vllm/issues/36311 — vLLM pluggable eviction RFC
- https://arxiv.org/abs/2406.12045 — τ-bench
