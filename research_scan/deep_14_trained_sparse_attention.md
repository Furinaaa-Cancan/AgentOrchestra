# Deep-Dive 14: Trained Sparse Attention (NSA, MoBA)

## 1. State of the field (2024 - 2026)

The defining shift of 2025 was moving attention sparsity from a post-hoc inference trick to a property the model is pretrained with.

- **NSA (Native Sparse Attention, DeepSeek + PKU + UW, Feb 2025)**. Hierarchical sparse strategy combining coarse token compression, fine token selection, and a sliding local window, all three gated per head. End-to-end trainable with custom Triton kernels. Reported maintain-or-exceed full-attention quality on general, long-context, and instruction-reasoning benchmarks; large wall-clock speedup at 64k decoding/forward/backward. Now ACL 2025 long paper. https://arxiv.org/abs/2502.11089
- **MoBA (Mixture of Block Attention, Moonshot AI, Feb 2025)**. Applies MoE-style routing to attention: context is partitioned into blocks, a learned gate sends each query to top-k blocks. Critically, MoBA can be toggled between sparse and dense per layer, which Moonshot uses for production Kimi long-context serving. https://arxiv.org/abs/2502.13189
- **MInference 1.0 (Microsoft, NeurIPS 2024 spotlight)**. The strongest *training-free* dynamic-sparse baseline. Identifies three head-level patterns (A-shape, Vertical-Slash, Block-Sparse), picks per-head pattern offline, runs sparse kernels online. Up to 10x prefill speedup on a single A100 at 1M tokens. https://arxiv.org/abs/2407.02490
- **The Sparse Frontier (Nawrot et al., Apr 2025, rev. Jan 2026)**. The largest empirical sweep of training-free sparse attention: 6 methods, sequences to 128k, sparsity to 0.95, 9 tasks. Three robust findings: larger-sparse beats smaller-dense at equal FLOPs; prefill vs decode favor different selection geometries; longer sequences tolerate more sparsity, so fixed budgets are suboptimal. https://arxiv.org/abs/2504.17768
- **DeepSeek-V3.2 / V4-Pro (late 2025 - early 2026)**. Production deployment of an indexer-selector "Compressed Sparse Attention" derived from NSA. V4-Pro is reported at ~27% of V3.2's per-token FLOPs and ~10% of the KV cache at million-token scale.
- **Adjacent**: SeerAttention (learned gating), Hash Attention (LSH-style retrieval-attention), Flash Sparse Attention / FSA (https://arxiv.org/abs/2508.18224) which is a faster kernel implementation of the NSA op (up to 3.5x kernel speedup, 1.25x e2e training over the original NSA kernel), and NOSA (offloadable NSA variant, https://arxiv.org/abs/2510.13602).

## 2. Training-time vs inference-time sparsity

Inference-time methods (H2O, SnapKV, StreamingLLM, MInference, SpargeAttention) attack a model whose weights were tuned to dense attention. They have to *guess* which tokens the dense model would have weighted, then discard the rest. Two structural costs follow:

1. **Phase-locked acceleration**. H2O/SnapKV eviction helps decode but not prefill; MInference's pattern search helps prefill but adds decode overhead. Neither cleanly accelerates both phases of long-CoT reasoning.
2. **Irreversible information loss**. Evicted KV cannot be reread. As The Sparse Frontier shows, the *set* of important tokens drifts across generation steps, so any greedy eviction is dominated at some sparsity threshold.

Training-time sparsity (NSA, MoBA, SeerAttention) lets the model *co-adapt* its representations to the sparse pattern. Empirically NSA matches or beats full attention at 27B-scale on long-context and reasoning, which no training-free method has done. Theoretically the result is unsurprising: dense pretraining produces a distribution of attention weights that is approximately power-law in magnitude but heavy-tailed in *which* tokens carry mass, so any fixed sparsifier loses signal. Training-time sparsifiers shape the tail itself.

The cost is brutal: you only get the win if you pretrain (or at least mid-train) under the sparse op. NSA's paper reports stable end-to-end pretraining, but the public reproductions all required custom Triton/CUTLASS kernels and careful balancing of the three NSA branches.

## 3. Hardware composition

NSA was designed against FlashAttention's tiling discipline: blockwise selection keeps arithmetic intensity high so Tensor Cores stay fed. FSA (Aug 2025) shows the original NSA kernel left significant performance on the table - alternative tiling reaches 1.6x average kernel speedup. FlashAttention-3 (Hopper, async + FP8, ~840 TFLOPs/s BF16, ~1.3 PFLOPs/s FP8) is largely orthogonal: NSA/MoBA call into FA-style kernels for the dense sub-blocks they keep. SageAttention (ICLR/ICML/NeurIPS 2025) is an INT8/FP8 quantized attention reaching 2-5x over FlashAttention; composing it with NSA selection is straightforward in principle (quantize the selected blocks) but no public paper has measured the combined accuracy degradation. That is a real gap.

## 4. Failure modes

- **Short-context overhead**. NSA, MoBA, SeerAttention all add gating/index-selection overhead that doesn't amortize below ~4k tokens. NSA papers concede sparse models are slower than dense at short context. For chat-heavy workloads this is a regression.
- **Training instability**. The NSA paper claims stability, but several reproductions report loss spikes when the compression branch dominates early in training; MoBA's gate is easier to stabilize but degrades when the block size is mis-chosen for the data distribution.
- **Downstream-task asymmetry**. Long-context QA (needle-in-haystack, RULER) is easy for sparse methods because answers are local. Long-CoT reasoning is harder: intermediate reasoning steps reference earlier steps non-locally, and any aggressive selection truncates the reasoning chain. Public NSA numbers on AIME24 and MATH500 are competitive but not dominant.
- **Distillation gap**. Distilling a dense teacher into a sparse student loses more than the reverse on reasoning traces. This is folklore-strong but under-measured.

## 5. Composition with reasoning

NSA and MoBA both report retained long-CoT capability at 32k+, but the published evaluations are thin: MATH500 and AIME24 on R1-distilled checkpoints, no GPQA-Diamond at long context, no agentic traces. The bigger open question is whether trained-sparse models can *learn* longer CoT than full-attention models, because cheaper attention means more tokens at fixed budget. This is the analog of "context = compute" for reasoning, and it is the most defensible bet for a follow-up paper.

## 6. Paper opportunities

**Proposal A. Sparse-Attention Reasoning Benchmark (SARB).** A head-to-head evaluation of NSA, MoBA, SeerAttention, MInference, H2O, SnapKV on long *reasoning* (not retrieval): long-CoT math (AIME24/25, PutnamBench), multi-hop code (SWE-bench Verified with long-repo context), and agentic traces (tau-bench at 64k+). Report Pareto frontier of accuracy vs prefill+decode wall-clock, *separating* prefill-bound and decode-bound regimes. Single-researcher feasible: all listed methods have open weights or are training-free patches over Llama-3.1-8B / Qwen2.5-7B. No pretraining required. Cost estimate: ~2k H100-hours, achievable on a rented 8xH100 node for ~2 weeks. This is the highest-leverage, lowest-risk paper in the cluster.

**Proposal B. Trained-Sparse x KV Eviction Interaction (crosses with deep_04).** Hypothesis: a model pretrained with NSA-style sparsity has *flatter* heavy-hitter distributions, so H2O-style eviction at inference loses more than on a dense baseline; conversely, MoBA-style block routing should compose cleanly with block-granular eviction. Mid-train a 1-3B model under NSA and MoBA for 20-50B tokens, then sweep H2O/SnapKV budgets at inference, measuring degradation on long-CoT. Honest cost: mid-training even at 1.3B for 20B tokens is ~4-8k H100-hours plus kernel engineering. **Likely out of reach for a single researcher without sponsored compute.** A weaker but defensible variant: use the public NSA-pretrained checkpoint if/when DeepSeek releases one, skip the pretraining, and only run the eviction sweep. That collapses to Proposal A's cost envelope.

## 7. Compute honesty

The headline result of this area - "train attention sparsity in, get full-attention quality with sparse-attention cost" - requires pretraining. A single researcher cannot reproduce NSA from scratch. The viable single-researcher contributions are: (1) evaluation papers that expose where the published claims fail (Proposal A), (2) kernel and systems contributions like FSA that don't require retraining, and (3) careful inference-time ablations on released checkpoints. Anything requiring pretraining-from-scratch is a lab paper, not an individual paper.

## Sources

- [NSA - arXiv 2502.11089](https://arxiv.org/abs/2502.11089)
- [MoBA - arXiv 2502.13189](https://arxiv.org/abs/2502.13189) / [MoonshotAI/MoBA GitHub](https://github.com/MoonshotAI/MoBA)
- [MInference 1.0 - NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/file/5dfbe6f5671e82c76841ba687a8a9ecb-Paper-Conference.pdf) / [microsoft/MInference](https://github.com/microsoft/MInference)
- [The Sparse Frontier - arXiv 2504.17768](https://arxiv.org/abs/2504.17768)
- [FlashAttention-3](https://tridao.me/publications/flash3/flash3.pdf)
- [SageAttention](https://github.com/thu-ml/SageAttention)
- [Flash Sparse Attention (FSA) - arXiv 2508.18224](https://arxiv.org/abs/2508.18224)
- [NOSA - arXiv 2510.13602](https://arxiv.org/abs/2510.13602)
- [H2O - NeurIPS 2023](https://proceedings.neurips.cc/paper_files/paper/2023/file/6ceefa7b15572587b78ecfcebb2827f8-Paper-Conference.pdf)
