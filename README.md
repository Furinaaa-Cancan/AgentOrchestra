# MyGO — Multi-agent Yielding Group Orchestra

一个**个人探索 / 学习项目**，围绕"多智能体协作做软件工程任务"这个题目做的一些代码实验和方法尝试。

> ⚠️ **项目状态：探索阶段已暂停**
> 本项目是作者出于兴趣自学 LangGraph、Claude CLI、多智能体编排和 SWE-bench 评测过程中积累的代码。经过若干轮实验后发现这个方向在 2024–2025 已被学术界系统性研究（Agentless, MAST, MASAI, Select-Then-Decompose 等），原创空间收敛。代码作为学习记录保留，未来可能复用其中的工程组件。

---

## 这个项目是什么

一套基于 LangGraph + Claude CLI 的多智能体编排框架，支持：

- **多个 CLI agent 并行**（builder / reviewer 等角色）
- **任务分解**（fixed 和 adaptive 两种策略）
- **Context Bridge**（基于 AST 提取接口契约，跨子任务传递信息）
- **SWE-bench Verified 评测管线**（Docker 隔离评测 + 本地 pytest fallback）
- **失败分析**（MAST taxonomy 编码模板 + Cohen's kappa）

## 它解决了什么 / 没解决什么

**有用的部分**：
- 一套相对完整的多智能体编排骨架，可以作为学习 LangGraph 多 agent 模式的参考
- SWE-bench adapter 和实验 runner 代码可以复用
- MAST 编码模板和 failure analysis 工具链

**没解决的部分**：
- v2 实验（自定义 9 个任务）显示自适应分解 + Context Bridge **没有稳定胜过单 agent baseline**
- v3 重新设计（SWE-bench Verified + McNemar 统计 + MAST）只跑了 pilot，没继续扩展
- 这条研究方向的核心命题（"多智能体分解何时有用"）已被 2025 年顶会论文系统回答

## 仓库结构

```
src/multi_agent/        # 主框架代码 (LangGraph orchestrator, CLI agents, context bridge)
scripts/                # 实验 runner、SWE-bench adapter、分析脚本
tests/                  # 单元 + 集成测试 (52 个测试文件)
agents/                 # Agent 配置 (agents.yaml, profiles)
prompts/                # Builder / reviewer prompt 模板
config/                 # 复杂度阈值等配置
skills/                 # 任务执行技能
task-templates/         # 任务模板 (api-endpoint, auth, bugfix, crud, refactor, test)
docs/                   # 架构和 API 文档
archive/                # 历史实验数据 (v1/v2/v3 results, MAST coding, 原始任务 artifacts)
```

## 安装与运行

```bash
# 环境
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 跑一个简单任务
multi-agent task new --template bugfix --task-id demo-01
multi-agent run demo-01

# 跑实验（需要 Claude CLI 已登录）
python scripts/experiment_runner_v2.py --condition single --runs 1
```

详细命令见 `docs/`。

## 实验记录（archive/）

- `archive/results/experiment_v2/` — 自定义 9 任务 × 4 条件 × 3 reps 的完整数据
- `archive/results/swebench_v1/` — SWE-bench Verified pilot（2 任务）
- `archive/results/failure_analysis/` — MAST 编码输出
- `archive/artifacts/` — 实验任务的原始代码 artifacts

数据以原始 JSON 保留，欢迎自取。

## 学到的东西

写代码之外的收获：

1. **顶会论文的 novelty bar 比想象中高**——一个看起来"没人做过"的方向，深入调研后会发现已有 5–10 篇 closely-related work
2. **negative result 不等于发表机会**——除非有方法论或机制层面的贡献
3. **engineering investment ≠ research investment**——把实验跑起来只是第一步，剩下 80% 的工作在论文写作和实验设计层面
4. **2025 年单 agent + 长上下文模型（Claude 1M、Gemini 2M）正在让"多智能体分解"这个 2023 年的命题变得过时**

## License

MIT。代码随便用，但请不要把"个人学习项目"包装成"研究成果"再二次发表。

## 致谢

感谢 Claude (Anthropic) 在本项目大量代码编写、文献调研、实验设计中的协助。
