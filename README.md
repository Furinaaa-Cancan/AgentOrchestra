<div align="center">

# AgentOrchestra

**Multi-Agent Orchestration for IDE-Based AI Coding Assistants**

*Coordinate Codex, Windsurf, and Antigravity through a shared workspace with LangGraph-powered state management*

[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-41%20passed-brightgreen.svg)]()

[English](#english) | [中文](#中文)

</div>

---

<a id="english"></a>

## What is AgentOrchestra?

AgentOrchestra is an open-source orchestration framework that coordinates multiple IDE-based AI coding assistants (Codex, Windsurf, Antigravity, etc.) to collaborate on software development tasks through a structured **Plan → Build → Review → Decide** pipeline.

Unlike traditional multi-agent frameworks that assume agents are API-callable LLMs, AgentOrchestra is designed for the real-world scenario where **AI agents live inside IDEs** and **humans are the communication bridge**. It minimizes manual friction to as few as **2 steps per agent cycle**.

### The Problem

Modern AI coding assistants (Windsurf Cascade, GitHub Codex, Cursor, etc.) are powerful individually, but coordinating them on a single task requires:
- Manually copying prompts between IDEs
- Tracking which agent should do what next
- Remembering to pass review feedback back to builders
- Managing retry budgets and timeouts
- No persistent state across sessions

### The Solution

AgentOrchestra provides:
- **Shared Workspace** (`.multi-agent/inbox/` and `outbox/`) — agents communicate via files
- **4-Node LangGraph Graph** — compact `plan → build → review → decide` cycle with automatic retry
- **Cross-Model Adversarial Review** — builder and reviewer are always different agents
- **Goal Dashboard** — real-time progress tracking in `dashboard.md`
- **Persistent Checkpoints** — resume from any point via SQLite-backed LangGraph checkpointer
- **2-Step CLI** — `ma go "requirement"` → `ma done`

## Research Foundation

This architecture is grounded in **7 peer-reviewed papers** and **3 industry benchmarks**:

| Paper | Venue | Key Insight Applied |
|-------|-------|-------------------|
| Evolving Orchestration | **NeurIPS 2025** | Compact cyclic graphs outperform complex ones |
| ChatDev | **ACL 2024** | Chat Chain role-pair dialogues |
| HULA | **ICSE 2025** | Human-in-the-loop with minimal friction |
| Agentless | **FSE 2025** | Simple 3-phase pipeline beats complex agents |
| OrchVis | arXiv 2025 | Goal-driven visualization + adaptive autonomy |
| ALMAS | arXiv 2025 | Agile role alignment for SE agents |
| MapCoder | **ACL 2024** | 4-agent recall→plan→code→debug pipeline |

> **Core finding**: RL-trained orchestrators converge to compact cyclic structures. Our 4-node graph is not a simplification — it's the empirically optimal structure.

## Architecture

```
                    ┌─────────┐
                    │  START   │
                    └────┬────┘
                         │
                    ┌────▼────┐
               ┌───▶│  plan   │  Load contract, pick agent, write inbox prompt
               │    └────┬────┘
               │         │
               │    ┌────▼────┐
               │    │  build  │  interrupt() — wait for builder agent
               │    └────┬────┘
               │         │
               │    ┌────▼────┐
               │    │ review  │  interrupt() — wait for reviewer agent
               │    └────┬────┘
               │         │
               │    ┌────▼────┐
               │    │ decide  │  approve → END, reject → retry
               │    └────┬────┘
               │         │
               │    ┌────▼────┐
               └────│  retry  │  (with reviewer feedback injected)
                    └─────────┘
```

### Communication Flow

```
Orchestrator                        IDE Agent (e.g. Windsurf)
    │                                     │
    │── write inbox/windsurf.md ─────────▶│  (user opens in IDE)
    │                                     │  (agent works...)
    │◀── ma done (submit output) ─────────│
    │                                     │
    │── write inbox/codex.md ────────────▶│  (reviewer, different agent)
    │                                     │
    │◀── ma done (submit review) ─────────│
    │                                     │
    │   [approve] → DONE                  │
    │   [reject]  → retry with feedback   │
```

### Shared Workspace Structure

```
.multi-agent/
├── inbox/              ← Agent prompts (orchestrator writes, agent reads)
│   ├── windsurf.md     ← Builder prompt with task details
│   └── codex.md        ← Reviewer prompt with builder output
├── outbox/             ← Agent outputs (agent writes, orchestrator reads)
│   ├── windsurf.json   ← Builder result
│   └── codex.json      ← Review decision
├── dashboard.md        ← Real-time goal progress panel
├── tasks/              ← Task state YAML files
├── history/            ← Conversation history archive
└── store.db            ← LangGraph checkpoint + audit storage
```

## Quick Start

### Installation

```bash
git clone https://github.com/Furinaaa-Cancan/AgentOrchestra.git
cd AgentOrchestra
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Usage

**Step 1: Start a task**

```bash
ma go "Implement POST /users endpoint with FastAPI" --skill code-implement
```

This will:
1. Load the `code-implement` skill contract
2. Select the best builder agent (e.g., `windsurf`)
3. Generate a structured prompt at `.multi-agent/inbox/windsurf.md`
4. Create a goal dashboard at `.multi-agent/dashboard.md`
5. Pause the graph, waiting for builder output

**Step 2: Let the agent work**

Open `.multi-agent/inbox/windsurf.md` in your IDE (or reference it via `@file`). The agent sees:
- Task description and completion criteria
- Quality checks to run
- Expected JSON output format
- Self-check instructions (Reflection pattern)

**Step 3: Submit the result**

```bash
ma done
```

This reads from `.multi-agent/outbox/windsurf.json` (or stdin), advances the graph to the `review` node, and automatically:
- Selects a **different** agent as reviewer (cross-model adversarial review)
- Generates a reviewer prompt with the builder's output included
- Pauses again, waiting for review

**Step 4: Submit the review**

```bash
ma done
```

If approved → task complete. If rejected → automatically retries with reviewer feedback injected into the next builder prompt.

### CLI Reference

| Command | Description |
|---------|-------------|
| `ma go "requirement"` | Start a new task from natural language |
| `ma done` | Submit agent output and advance the graph |
| `ma status` | Show current task status |
| `ma cancel` | Cancel the current task |

### Example: Full Cycle

```bash
$ ma go "Implement input validation for user registration" --skill code-implement
🚀 Starting task: task-a1b2c3d4
   Skill: code-implement
⏸️  Graph paused at: build
   Agent: windsurf
   Inbox: .multi-agent/inbox/windsurf.md

# ... agent works, outputs to outbox ...

$ ma done
📤 Submitting output for task task-a1b2c3d4 (agent: windsurf)
⏸️  Graph paused at: review
   Agent: codex
   Inbox: .multi-agent/inbox/codex.md

# ... reviewer reviews ...

$ ma done
📤 Submitting output for task task-a1b2c3d4 (agent: codex)
🏁 Task finished. Status: approved
```

## Project Structure

```
AgentOrchestra/
├── pyproject.toml                  # Package config, `ma` CLI entry point
├── src/multi_agent/
│   ├── schema.py                   # Pydantic models (Task, SkillContract, AgentOutput)
│   ├── graph.py                    # 4-node LangGraph workflow
│   ├── cli.py                      # CLI: ma go / ma done / ma status / ma cancel
│   ├── config.py                   # Unified path configuration
│   ├── contract.py                 # Skill contract loader + validation
│   ├── router.py                   # Agent routing (cross-model adversarial review)
│   ├── workspace.py                # .multi-agent/ directory management
│   ├── prompt.py                   # Jinja2 prompt rendering
│   ├── dashboard.py                # Goal dashboard generator
│   └── watcher.py                  # File watcher (outbox polling)
├── templates/
│   ├── builder.md.j2               # Builder prompt template
│   └── reviewer.md.j2              # Reviewer prompt template
├── skills/                         # Skill contracts (YAML)
│   ├── code-implement/contract.yaml
│   ├── test-and-review/contract.yaml
│   └── task-decompose/contract.yaml
├── agents/profiles.json            # Agent capability profiles
├── tests/                          # 41 tests
└── LICENSE                         # CC BY-NC-SA 4.0
```

## Key Design Decisions

| Decision | Rationale | Academic Source |
|----------|-----------|---------------|
| 4 graph nodes (not 15) | RL-trained orchestrators converge to compact cycles | NeurIPS 2025 |
| File-based communication | Works with any IDE agent, zero dependencies | ALMAS (arXiv 2025) |
| Builder ≠ Reviewer | Cross-model adversarial review improves quality | Metaswarm pattern |
| Retry with feedback injection | Automatic iterative refinement loop | AgentMesh (arXiv 2025) |
| Goal dashboard (not state machine) | Users care about goals, not internal states | OrchVis (arXiv 2025) |
| Jinja2 Chat Chain prompts | Structured role-pair dialogues with Reflection | ChatDev (ACL 2024) |
| SQLite checkpointer | Persistent state, resume from any point | LangGraph best practice |

## Skill Contracts

Each skill defines a contract in YAML:

```yaml
id: code-implement
version: 1.0.0
description: Apply scoped code changes with strict locking and check execution.
quality_gates: [lint, unit_test, artifact_checksum]
timeouts:
  run_sec: 1800
  verify_sec: 600
retry:
  max_attempts: 2
  backoff: linear
compatibility:
  supported_agents: [codex, windsurf, antigravity]
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## License

This project is licensed under **CC BY-NC-SA 4.0** (Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International).

- **You may**: share, adapt, remix for non-commercial purposes
- **You may NOT**: use this for commercial purposes
- **You must**: give attribution, share derivatives under the same license

See [LICENSE](LICENSE) for details.

---

<a id="中文"></a>

<div align="center">

# AgentOrchestra

**面向 IDE AI 编程助手的多智能体编排框架**

*通过共享工作区协调 Codex、Windsurf 和 Antigravity，基于 LangGraph 状态管理*

</div>

## 这是什么？

AgentOrchestra 是一个开源的多智能体编排框架，用于协调多个 IDE 内置的 AI 编程助手（Codex、Windsurf、Antigravity 等）通过结构化的 **Plan → Build → Review → Decide** 管道协作完成软件开发任务。

与传统多智能体框架假设 agent 可通过 API 调用不同，AgentOrchestra 专为**真实场景**设计——**AI agent 存在于 IDE 中**，**人类是通信桥梁**。每个 agent 周期最少只需 **2 步操作**。

### 解决的问题

现代 AI 编程助手（Windsurf Cascade、GitHub Codex、Cursor 等）单独使用时很强大，但协调它们完成同一个任务需要：
- 在 IDE 之间手动复制粘贴 prompt
- 追踪下一步该由哪个 agent 执行
- 记住将审查反馈传递给 builder
- 管理重试预算和超时
- 会话间无持久化状态

### 解决方案

AgentOrchestra 提供：
- **共享工作区** (`.multi-agent/inbox/` 和 `outbox/`) — agent 通过文件通信
- **4 节点 LangGraph 图** — 紧凑的 `plan → build → review → decide` 循环，支持自动重试
- **跨模型对抗审查** — builder 和 reviewer 始终是不同的 agent
- **目标面板** — 在 `dashboard.md` 中实时追踪进度
- **持久化检查点** — 通过 SQLite 支持的 LangGraph checkpointer 从任意点恢复
- **2 步 CLI** — `ma go "需求描述"` → `ma done`

## 研究基础

本架构基于 **7 篇同行评审论文** 和 **3 个业界标杆**：

| 论文 | 发表 | 应用的核心洞察 |
|------|------|--------------|
| Evolving Orchestration | **NeurIPS 2025** | 紧凑循环图优于复杂图 |
| ChatDev | **ACL 2024** | Chat Chain 角色对话链 |
| HULA | **ICSE 2025** | 人在回路，最小化摩擦 |
| Agentless | **FSE 2025** | 简单 3 阶段管道击败复杂 agent |
| OrchVis | arXiv 2025 | 目标驱动可视化 + 自适应自治 |
| ALMAS | arXiv 2025 | 敏捷角色对齐 |
| MapCoder | **ACL 2024** | 4-agent recall→plan→code→debug 管道 |

> **核心发现**：RL 训练的编排器自动收敛到紧凑循环结构。我们的 4 节点图不是简化——而是实证最优结构。

## 架构

```
                    ┌─────────┐
                    │  START   │
                    └────┬────┘
                         │
                    ┌────▼────┐
               ┌───▶│  plan   │  加载合约，选择 agent，写入 inbox prompt
               │    └────┬────┘
               │         │
               │    ┌────▼────┐
               │    │  build  │  interrupt() — 等待 builder agent
               │    └────┬────┘
               │         │
               │    ┌────▼────┐
               │    │ review  │  interrupt() — 等待 reviewer agent
               │    └────┬────┘
               │         │
               │    ┌────▼────┐
               │    │ decide  │  approve → 结束, reject → 重试
               │    └────┬────┘
               │         │
               │    ┌────▼────┐
               └────│  retry  │  (注入 reviewer 反馈)
                    └─────────┘
```

### 通信流程

```
编排器 (Orchestrator)                  IDE Agent (如 Windsurf)
    │                                     │
    │── 写 inbox/windsurf.md ────────────▶│  (用户在 IDE 中打开)
    │                                     │  (agent 工作...)
    │◀── ma done (提交输出) ──────────────│
    │                                     │
    │── 写 inbox/codex.md ──────────────▶│  (reviewer，不同 agent)
    │                                     │
    │◀── ma done (提交审查) ──────────────│
    │                                     │
    │   [approve] → 完成                  │
    │   [reject]  → 带反馈重试            │
```

## 快速开始

### 安装

```bash
git clone https://github.com/Furinaaa-Cancan/AgentOrchestra.git
cd AgentOrchestra
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### 使用

**第 1 步：启动任务**

```bash
ma go "实现 POST /users endpoint" --skill code-implement
```

这会自动完成：
1. 加载 `code-implement` skill 合约
2. 选择最佳 builder agent（如 `windsurf`）
3. 在 `.multi-agent/inbox/windsurf.md` 生成结构化 prompt
4. 在 `.multi-agent/dashboard.md` 创建目标面板
5. 暂停图，等待 builder 输出

**第 2 步：让 agent 工作**

在 IDE 中打开 `.multi-agent/inbox/windsurf.md`（或通过 `@file` 引用）。Agent 会看到：
- 任务描述和完成标准
- 需要运行的质量检查
- 预期的 JSON 输出格式
- 自检指令（Reflection 模式）

**第 3 步：提交结果**

```bash
ma done
```

自动读取 `.multi-agent/outbox/windsurf.json`（或从 stdin），推进图到 `review` 节点，并自动：
- 选择一个**不同的** agent 作为 reviewer（跨模型对抗审查）
- 生成包含 builder 输出的 reviewer prompt
- 再次暂停，等待审查

**第 4 步：提交审查**

```bash
ma done
```

如果 approve → 任务完成。如果 reject → 自动将 reviewer 反馈注入下一轮 builder prompt 并重试。

### 完整示例

```bash
$ ma go "实现用户注册的输入校验" --skill code-implement
🚀 Starting task: task-a1b2c3d4
   Skill: code-implement
⏸️  Graph paused at: build
   Agent: windsurf
   Inbox: .multi-agent/inbox/windsurf.md

# ... agent 工作，输出到 outbox ...

$ ma done
📤 Submitting output for task task-a1b2c3d4 (agent: windsurf)
⏸️  Graph paused at: review
   Agent: codex                    # 自动选择不同 agent 审查
   Inbox: .multi-agent/inbox/codex.md

# ... reviewer 审查 ...

$ ma done
📤 Submitting output for task task-a1b2c3d4 (agent: codex)
🏁 Task finished. Status: approved
```

### CLI 命令

| 命令 | 说明 |
|------|------|
| `ma go "需求"` | 从自然语言启动新任务 |
| `ma done` | 提交 agent 输出并推进图 |
| `ma status` | 查看当前任务状态 |
| `ma cancel` | 取消当前任务 |

## 关键设计决策

| 决策 | 原因 | 学术来源 |
|------|------|---------|
| 4 个图节点（不是 15 个） | RL 训练的编排器收敛到紧凑循环 | NeurIPS 2025 |
| 文件通信 | 适用于任何 IDE agent，零依赖 | ALMAS (arXiv 2025) |
| Builder ≠ Reviewer | 跨模型对抗审查提高质量 | Metaswarm 模式 |
| 带反馈的自动重试 | 迭代精炼循环 | AgentMesh (arXiv 2025) |
| 目标面板（不是状态机） | 用户关心目标进度，不是内部状态 | OrchVis (arXiv 2025) |
| Jinja2 Chat Chain prompt | 结构化角色对话 + Reflection | ChatDev (ACL 2024) |
| SQLite checkpointer | 持久化状态，任意点恢复 | LangGraph 最佳实践 |

## 运行测试

```bash
pip install -e ".[dev]"
pytest tests/ -v
# 41 tests passed
```

## 许可证

本项目采用 **CC BY-NC-SA 4.0**（知识共享 署名-非商业性使用-相同方式共享 4.0 国际）许可证。

- **你可以**：在非商业用途下分享、改编、混合
- **你不可以**：将本项目用于商业目的
- **你必须**：注明出处，以相同许可证分享衍生作品

详见 [LICENSE](LICENSE)。

---

<div align="center">

Made with determination by [@Furinaaa-Cancan](https://github.com/Furinaaa-Cancan)

</div>
