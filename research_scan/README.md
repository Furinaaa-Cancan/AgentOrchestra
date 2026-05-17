# LLM Research Direction Scan — 2026.05

围绕 2025–2026 LLM 研究地图的多 agent 并行扫描成果。**19 份独立调研 + 1 份顶层综合 = 20 个文件**。

> ⚠️ **元结论**（多个独立 agent 在不同 deep dive 里共振得出）：
> 第 11、12、13 个 deep-dive agent **独立给出同一个建议**——继续 scan 的边际收益已经低于开始最强候选方向的边际收益。你的最大杠杆不是再扫一个领域，而是把 `archive/` 里 v3 SWE-bench + MAST infra 复用到一个具体的诊断方法学论文。

---

## 文件索引

### 第一层：5 个切面基础扫描

| 文件 | 切面 |
|---|---|
| [01_foundation_models.md](01_foundation_models.md) | 基础模型 / 架构 / 预训练 |
| [02_reasoning_agents.md](02_reasoning_agents.md) | 推理 & Agent |
| [03_alignment_safety_eval.md](03_alignment_safety_eval.md) | 对齐 / 安全 / 评测 / 可解释 |
| [04_applications_domains.md](04_applications_domains.md) | 应用 & 领域 |
| [05_efficiency_systems.md](05_efficiency_systems.md) | 效率 / 推理系统 / 硬件 |

### 第二层：14 个交叉地带深挖

| 文件 | 主题 |
|---|---|
| [deep_01_agent_bench_integrity.md](deep_01_agent_bench_integrity.md) | Agent benchmark 完整性 / reward-hacking 诊断 |
| [deep_02_latent_cot_interpretability.md](deep_02_latent_cot_interpretability.md) | Latent CoT × 可解释性 / 安全 |
| [deep_03_cua_security.md](deep_03_cua_security.md) | Computer-use agent OS 层攻击面 |
| [deep_04_kv_eviction_agent_traces.md](deep_04_kv_eviction_agent_traces.md) | KV eviction × agent traces |
| [deep_05_prm_transfer.md](deep_05_prm_transfer.md) | PRM 跨域迁移 & reward-hacking |
| [deep_06_sae_credibility.md](deep_06_sae_credibility.md) | SAE 信用危机 & 路径 |
| [deep_07_synthetic_data_collapse.md](deep_07_synthetic_data_collapse.md) | 合成数据 collapse |
| [deep_08_verified_codegen.md](deep_08_verified_codegen.md) | Verified codegen (Lean/Dafny/Verus) |
| [deep_09_ai_scientist_audit.md](deep_09_ai_scientist_audit.md) | AI Scientist 严谨性审计 |
| [deep_10_diffusion_llms.md](deep_10_diffusion_llms.md) | Diffusion LLM vs AR |
| [deep_11_rl_serving.md](deep_11_rl_serving.md) | RL serving infrastructure |
| [deep_12_on_policy_distillation.md](deep_12_on_policy_distillation.md) | On-Policy Distillation |
| [deep_13_long_context_reasoning.md](deep_13_long_context_reasoning.md) | 长上下文推理评测 |
| [deep_14_trained_sparse_attention.md](deep_14_trained_sparse_attention.md) | Trained sparse attention (NSA/MoBA) |

---

## 最终综合：3 个 Tier × 14 个候选

按"**与你现有 infra 复用度 × 创新性 × 算力可行性 × 竞争风险**"重排。

### 🟢 Tier S — 直接复用你的 SWE-bench + MAST infra，低算力，6–10 周可发

| # | 方向 | 来源 | 核心 |
|---|---|---|---|
| **1** | **Agent Benchmark 差分审计** | [deep_01](deep_01_agent_bench_integrity.md) | 量化 SOTA 模型在 SWE-bench/OSWorld 的得分有 X% 来自 reward-hacking。Anthropic 内部可能有未发，但你能占 "first **reproducible** audit" 标签 |
| **2** | **PRM × Multi-agent Traces 杂交** | [deep_05](deep_05_prm_transfer.md) + 你 archive/ | Agent 在 deep_05 里直接建议：用 math PRM 给你 archive/ 的 adaptive_bridge agent traces 打分，直接测 style-as-hack-vector。**把你"暂停"的多智能体老线和 PRM 新线合成一篇** |
| **3** | **REPOREASON Failure-Mode Taxonomy** | [deep_13](deep_13_long_context_reasoning.md) Proposal B | 不是 benchmark 而是 *failure mode* 分类——和 MAST 同形态。Repo-scale 推理失败的 reproducible instances |

### 🟡 Tier A — 需要切到开源模型或加一层 testbed，6 周–4 月，中等算力

| # | 方向 | 来源 | 风险 |
|---|---|---|---|
| 4 | **OPD-Atlas 失败模式取证** | [deep_12](deep_12_on_policy_distillation.md) Proposal B | 接 MAST 诊断风格；工业领先学术 12–18 月，2026 是 catch-up year |
| 5 | **Diffusion-as-Latent-CoT for Code Repair** | [deep_10](deep_10_diffusion_llms.md) Proposal B | 微调 DiffuCoder-7B on SWE-bench；测迭代精炼能否胜过 AR 的 phantom-edit 失败 |
| 6 | **KV Eviction × Agent Traces 失败图谱** | [deep_04](deep_04_kv_eviction_agent_traces.md) Paper A | 切到 Qwen3-Coder-30B；UCLA 2–4 月可能 scoop |
| 7 | **CUA OS-Inject Benchmark** | [deep_03](deep_03_cua_security.md) Proposal A | 需搭 OS-level testbed；NIST CAISI / Brave / Meta 都在做 |

### 🔴 Tier B — 高 novelty 但竞争激烈或算力门槛过高

| # | 方向 | 拒绝/降级理由 |
|---|---|---|
| 8 | Latent CoT × Monitorability ([deep_02](deep_02_latent_cot_interpretability.md)) | SPAR Spring'26 学生正面竞争 |
| 9 | SAE Interp-Bench ([deep_06](deep_06_sae_credibility.md)) | DeepMind 已降级 SAE 研究，"audit 论文会过时" |
| 10 | Verified Codegen 跨形式化迁移 ([deep_08](deep_08_verified_codegen.md)) | Lean 已饱和；Dafny/Verus 需要形式方法背景 |
| 11 | AI Scientist Novelty Audit ([deep_09](deep_09_ai_scientist_audit.md)) | 非领域专家挑战 GNoME/A-Lab 不现实 |
| 12 | RL Async 失败相图 ([deep_11](deep_11_rl_serving.md)) | 仍需 2000+ H100 小时；系统论文引用周期 6 月即烂 |
| 13 | Synthetic Data Phase Diagram ([deep_07](deep_07_synthetic_data_collapse.md)) | 拥挤；Strong Model Collapse 已占严谨理论位 |
| 14 | Trained Sparse Attention ([deep_14](deep_14_trained_sparse_attention.md)) | 有趣的版本需要预训练——单作者做不到 |

---

## 给读者的最后判断

如果你只想做一件事：

> **Tier S #1 (Agent Bench 差分审计) + Tier S #2 (PRM × multi-agent traces 杂交)**——这两个能合并成同一篇论文，主标题 *"Differential Audit of Agent Benchmarks: A Process-Reward-Based Method"*，副标题挂"using SWE-bench Verified and MAST"。

- 完美复用你 archive/ 里的 v3 infra + adaptive_bridge traces + MAST coding 工具
- 把 v2 negative result 当 case study A，让"暂停的多智能体研究"反过来成为新论文的数据资产
- 6–8 周可达 NeurIPS Evaluating Agents workshop（先）→ ICLR'27 main
- 即便结果是小 Δ，pre-registration 让负面结果也 publishable

**多个独立 agent 在 5 个不同 deep dive 里都指向同一个杠杆点**：你的边际优势是 MAST 风格的 agent 诊断方法学，不是再扫一个新方向。继续扫的边际 EV 已转负。

如果你不打算追这个方向，那 **`research_scan/` 仍是个有用的 LLM 研究地图**——14 个 niche 各有具体论文 proposal，可以当 personal reading guide。

---

## 不推荐方向（5 份扫描 + 14 份深挖 一致标记 SATURATED）

- ❌ 多智能体分解 / debate / role-play（你刚撤的方向）
- ❌ Token-CoT 变种（ToT / GoT）
- ❌ DPO 偏好优化变种
- ❌ HumanEval / MBPP / MedQA MCQ benchmark 上的新 method
- ❌ Speculative decoding 新变种（EAGLE-3 已是天花板）
- ❌ 单作者从零做 foundation model 架构 / 预训练（compute floor 太高）
- ❌ 纯 SSM（被 NeurIPS'25 判死刑）
- ❌ Lean 定理证明新 prover（miniF2F 99.2% 已饱和）
- ❌ AI Scientist 在 ML benchmark 上做的"自发现"（GNoME 已被三方拆穿）
- ❌ SAE 命名特征论文（DeepMind 已降级该研究方向）
