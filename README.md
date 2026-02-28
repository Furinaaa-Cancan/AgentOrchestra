<div align="center">

# AgentOrchestra

**IDE-Agnostic Multi-Agent Orchestration Framework**

*Coordinate ANY combination of AI coding assistants — Windsurf, Cursor, Codex, Kiro, Antigravity, Copilot, Aider, and more — through role-based collaboration with LangGraph-powered state management*

[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-41%20passed-brightgreen.svg)]()

[English](#english) | [中文](#中文)

</div>

---

<a id="english"></a>

## What is AgentOrchestra?

AgentOrchestra is an open-source orchestration framework that coordinates multiple IDE-based AI coding assistants to collaborate on software tasks through a **Plan → Build → Review → Decide** pipeline.

### Core Design Principle

> **The system doesn't care which IDE you use. It only cares about ROLES.**

Unlike frameworks that hardcode specific AI tools, AgentOrchestra uses **role-based communication**:
- `builder.md` — prompt for whoever is building (could be Windsurf, Cursor, Kiro, anything)
- `reviewer.md` — prompt for whoever is reviewing (must be a different IDE)
- `TASK.md` — single entry point that tells ANY IDE what's happening and what to do

You decide which IDE fills which role. The system handles everything else.

### The Problem

Modern AI coding assistants are powerful individually, but coordinating them requires:
- Manually copying prompts between IDEs
- Tracking whose turn it is
- Passing review feedback back to builders
- Managing retry budgets
- No persistent state across sessions

### The Solution

- **Role-Based Workspace** — `inbox/builder.md` and `inbox/reviewer.md` (not tied to any specific IDE)
- **TASK.md** — open in any IDE, instantly know what to do
- **`--builder` / `--reviewer` flags** — you choose which IDE does what
- **4-Node LangGraph Graph** — compact `plan → build → review → decide` cycle
- **Cross-Model Adversarial Review** — builder and reviewer must be different IDEs
- **Persistent Checkpoints** — resume from any point via SQLite
- **2-Step CLI** — `ma go "requirement"` → `ma done`

### Supported IDEs

Any IDE with an AI assistant works. Tested with:

| IDE | Builder | Reviewer | Notes |
|-----|---------|----------|-------|
| **Windsurf** (Cascade) | ✅ | ✅ | Full support |
| **Cursor** | ✅ | ✅ | Full support |
| **GitHub Codex** | ✅ | ✅ | Full support |
| **Kiro** | ✅ | ✅ | Full support |
| **Antigravity** | ✅ | ✅ | Full support |
| **Copilot** | ✅ | ✅ | Via @file reference |
| **Aider** | ✅ | ✅ | CLI-based |
| **Cline** | ✅ | ✅ | Full support |
| *Any other IDE* | ✅ | ✅ | Just add to agents.yaml |

## Architecture

### Communication Flow

```
  You (in IDE A: builder)           You (in IDE B: reviewer)
       │                                  │
       │  ┌──────────────────────┐        │
       │  │   .multi-agent/      │        │
       │  │   ├── TASK.md ◄──────┼────────┤  ← Both IDEs read this
       │  │   ├── inbox/         │        │
       ├──┼──►│   ├── builder.md │        │  ← Builder reads this
       │  │   │   └── reviewer.md├────────┤  ← Reviewer reads this
       │  │   ├── outbox/        │        │
       ├──┼──►│   ├── builder.json        │  ← Builder writes this
       │  │   │   └── reviewer.json◄──────┤  ← Reviewer writes this
       │  │   └── dashboard.md   │        │
       │  └──────────────────────┘        │
       │                                  │
       │         ma done ─────────────────│
       │                                  │
```

### 4-Node Graph

```
                    ┌─────────┐
                    │  START   │
                    └────┬────┘
                         │
                    ┌────▼────┐
               ┌───▶│  plan   │  Resolve roles, write builder prompt
               │    └────┬────┘
               │         │
               │    ┌────▼────┐
               │    │  build  │  interrupt() — wait for builder
               │    └────┬────┘
               │         │
               │    ┌────▼────┐
               │    │ review  │  interrupt() — wait for reviewer
               │    └────┬────┘
               │         │
               │    ┌────▼────┐
               │    │ decide  │  approve → END, reject → retry
               │    └────┬────┘
               │         │
               └─────────┘  (with reviewer feedback injected)
```

## Quick Start

### Installation

```bash
git clone https://github.com/Furinaaa-Cancan/AgentOrchestra.git
cd AgentOrchestra
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Configure Your IDEs

Edit `agents/agents.yaml`:

```yaml
agents:
  - id: windsurf
    capabilities: [planning, implementation, testing, docs]
  - id: cursor
    capabilities: [planning, implementation, testing, review, docs]
  - id: kiro
    capabilities: [planning, implementation, testing, review]
  # Add any IDE you want here

defaults:
  builder: windsurf    # Which IDE builds by default
  reviewer: cursor     # Which IDE reviews by default
```

### Usage

**Step 1: Start a task — specify which IDEs to use**

```bash
# Use defaults from agents.yaml
ma go "Implement POST /users endpoint"

# Or explicitly choose IDEs
ma go "Implement POST /users endpoint" --builder windsurf --reviewer cursor

# Or any combination
ma go "Fix auth bug" --builder kiro --reviewer codex
```

**Step 2: Open TASK.md in your builder IDE**

The file `.multi-agent/TASK.md` tells you exactly what to do:

```
## Current State
| Current Step | BUILDER |
| Builder      | windsurf |
| Reviewer     | cursor |

## What to Do Now
If you are windsurf (or whichever IDE is acting as builder):
1. Read the prompt: .multi-agent/inbox/builder.md
2. Do the implementation work
3. Save output to: .multi-agent/outbox/builder.json
4. Run: ma done
```

**Step 3: Submit and advance**

```bash
ma done    # Reads from outbox/builder.json automatically
```

The system advances to the review phase. TASK.md updates to show it's the reviewer's turn.

**Step 4: Open TASK.md in your reviewer IDE**

```bash
ma done    # Reads from outbox/reviewer.json automatically
```

If approved → task complete. If rejected → retries with feedback.

### Full Example

```bash
$ ma go "Add input validation" --builder windsurf --reviewer cursor
🚀 Starting task: task-a1b2c3d4
   Skill: code-implement
⏸️  Graph paused at: build
   Role: builder
   IDE:  windsurf
   Inbox: .multi-agent/inbox/builder.md

# ... windsurf works, saves to outbox/builder.json ...

$ ma done
📤 Submitting builder output for task task-a1b2c3d4 (IDE: windsurf)
⏸️  Graph paused at: review
   Role: reviewer
   IDE:  cursor
   Inbox: .multi-agent/inbox/reviewer.md

# ... cursor reviews, saves to outbox/reviewer.json ...

$ ma done
📤 Submitting reviewer output for task task-a1b2c3d4 (IDE: cursor)
🏁 Task finished. Status: approved
```

### CLI Reference

| Command | Description |
|---------|-------------|
| `ma go "requirement"` | Start a new task |
| `ma go "req" --builder X --reviewer Y` | Start with specific IDEs |
| `ma done` | Submit output and advance |
| `ma status` | Show current task status |
| `ma cancel` | Cancel the current task |

## Research Foundation

This architecture is grounded in **7 peer-reviewed papers**:

| Paper | Venue | Key Insight Applied |
|-------|-------|-------------------|
| Evolving Orchestration | **NeurIPS 2025** | Compact cyclic graphs outperform complex ones |
| ChatDev | **ACL 2024** | Chat Chain role-pair dialogues |
| HULA | **ICSE 2025** | Human-in-the-loop with minimal friction |
| Agentless | **FSE 2025** | Simple 3-phase pipeline beats complex agents |
| OrchVis | arXiv 2025 | Goal-driven visualization + adaptive autonomy |
| ALMAS | arXiv 2025 | Agile role alignment for SE agents |
| MapCoder | **ACL 2024** | 4-agent recall→plan→code→debug pipeline |

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Role-based, not IDE-based** | Works with any IDE, no code changes needed |
| **TASK.md universal entry** | Any IDE reads one file to understand state |
| **4 graph nodes** | RL-trained orchestrators converge to compact cycles |
| **Builder ≠ Reviewer** | Cross-model adversarial review improves quality |
| **File-based communication** | Zero dependencies, works everywhere |
| **User picks IDEs** | System manages roles, user manages tools |
| **SQLite checkpointer** | Persistent state, resume from any point |

## Workspace Structure

```
.multi-agent/
├── TASK.md             ← Universal entry point (any IDE reads this)
├── inbox/
│   ├── builder.md      ← Builder prompt (role-based, not IDE-based)
│   └── reviewer.md     ← Reviewer prompt
├── outbox/
│   ├── builder.json    ← Builder output
│   └── reviewer.json   ← Reviewer output
├── dashboard.md        ← Progress panel
├── tasks/              ← Task state markers
├── history/            ← Conversation archive
└── store.db            ← LangGraph checkpoint storage
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
# 41 tests passed
```

## License

**CC BY-NC-SA 4.0** — You may share and adapt for non-commercial purposes with attribution. See [LICENSE](LICENSE).

---

<a id="中文"></a>

<div align="center">

# AgentOrchestra

**IDE 无关的多智能体编排框架**

*协调任意 AI 编程助手组合 — Windsurf、Cursor、Codex、Kiro、Antigravity、Copilot、Aider 等 — 通过基于角色的协作*

</div>

## 这是什么？

AgentOrchestra 是一个开源的多智能体编排框架，通过 **Plan → Build → Review → Decide** 管道协调多个 IDE 内置的 AI 编程助手协作完成任务。

### 核心设计原则

> **系统不关心你用哪个 IDE。系统只关心角色。**

与硬编码特定 AI 工具的框架不同，AgentOrchestra 使用**基于角色的通信**：
- `builder.md` — 给 builder 的 prompt（可以是 Windsurf、Cursor、Kiro，任何 IDE）
- `reviewer.md` — 给 reviewer 的 prompt（必须是不同的 IDE）
- `TASK.md` — 统一入口文件，任何 IDE 打开就知道当前状态和下一步

你决定哪个 IDE 扮演哪个角色，系统处理其他一切。

### 解决的问题

- 在 IDE 之间手动复制粘贴 prompt
- 追踪轮到谁了
- 记住将审查反馈传递给 builder
- 管理重试预算
- 会话间无持久化状态

### 解决方案

- **基于角色的工作区** — `inbox/builder.md` 和 `inbox/reviewer.md`（不绑定任何特定 IDE）
- **TASK.md** — 在任何 IDE 中打开，立刻知道该做什么
- **`--builder` / `--reviewer` 参数** — 你选择哪个 IDE 做什么
- **4 节点 LangGraph 图** — 紧凑的循环，支持自动重试
- **跨模型对抗审查** — builder 和 reviewer 必须是不同的 IDE
- **持久化检查点** — 从任意点恢复
- **2 步 CLI** — `ma go "需求"` → `ma done`

### 支持的 IDE

任何带 AI 助手的 IDE 都可以。已测试：

| IDE | Builder | Reviewer |
|-----|---------|----------|
| **Windsurf** (Cascade) | ✅ | ✅ |
| **Cursor** | ✅ | ✅ |
| **GitHub Codex** | ✅ | ✅ |
| **Kiro** | ✅ | ✅ |
| **Antigravity** | ✅ | ✅ |
| **Copilot** | ✅ | ✅ |
| **Aider** | ✅ | ✅ |
| **Cline** | ✅ | ✅ |
| *任何其他 IDE* | ✅ | ✅ |

## 快速开始

### 安装

```bash
git clone https://github.com/Furinaaa-Cancan/AgentOrchestra.git
cd AgentOrchestra
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### 配置你的 IDE

编辑 `agents/agents.yaml`：

```yaml
agents:
  - id: windsurf
    capabilities: [planning, implementation, testing, docs]
  - id: cursor
    capabilities: [planning, implementation, testing, review, docs]
  # 在这里添加任何 IDE

defaults:
  builder: windsurf    # 默认哪个 IDE 做 builder
  reviewer: cursor     # 默认哪个 IDE 做 reviewer
```

### 使用

**第 1 步：启动任务 — 指定用哪些 IDE**

```bash
# 使用 agents.yaml 中的默认值
ma go "实现 POST /users endpoint"

# 或明确指定 IDE
ma go "实现 POST /users endpoint" --builder windsurf --reviewer cursor

# 任意组合
ma go "修复登录 bug" --builder kiro --reviewer codex
```

**第 2 步：在 builder IDE 中打开 TASK.md**

`.multi-agent/TASK.md` 告诉你该做什么：

```
## 当前状态
| 当前步骤 | BUILDER |
| Builder  | windsurf |
| Reviewer | cursor |

## 下一步
如果你是 windsurf（或充当 builder 的 IDE）：
1. 读取 prompt: .multi-agent/inbox/builder.md
2. 完成实现工作
3. 保存输出到: .multi-agent/outbox/builder.json
4. 运行: ma done
```

**第 3 步：提交并推进**

```bash
ma done    # 自动从 outbox/builder.json 读取
```

系统推进到审查阶段。TASK.md 自动更新，显示轮到 reviewer 了。

**第 4 步：在 reviewer IDE 中打开 TASK.md**

```bash
ma done    # 自动从 outbox/reviewer.json 读取
```

approve → 任务完成。reject → 带反馈自动重试。

### 完整示例

```bash
$ ma go "添加输入校验" --builder windsurf --reviewer cursor
🚀 Starting task: task-a1b2c3d4
⏸️  Graph paused at: build
   Role: builder
   IDE:  windsurf
   Inbox: .multi-agent/inbox/builder.md

# ... windsurf 工作，保存到 outbox/builder.json ...

$ ma done
📤 Submitting builder output (IDE: windsurf)
⏸️  Graph paused at: review
   Role: reviewer
   IDE:  cursor
   Inbox: .multi-agent/inbox/reviewer.md

# ... cursor 审查，保存到 outbox/reviewer.json ...

$ ma done
📤 Submitting reviewer output (IDE: cursor)
�� Task finished. Status: approved
```

### CLI 命令

| 命令 | 说明 |
|------|------|
| `ma go "需求"` | 启动新任务 |
| `ma go "需求" --builder X --reviewer Y` | 指定 IDE |
| `ma done` | 提交输出并推进 |
| `ma status` | 查看当前状态 |
| `ma cancel` | 取消任务 |

## 关键设计决策

| 决策 | 原因 |
|------|------|
| **基于角色，不基于 IDE** | 适用于任何 IDE，无需改代码 |
| **TASK.md 统一入口** | 任何 IDE 读一个文件就懂状态 |
| **4 个图节点** | RL 编排器收敛到紧凑循环 |
| **Builder ≠ Reviewer** | 跨模型对抗审查提高质量 |
| **文件通信** | 零依赖，到处能用 |
| **用户选 IDE** | 系统管角色，用户管工具 |
| **SQLite checkpointer** | 持久化状态，任意恢复 |

## 运行测试

```bash
pip install -e ".[dev]"
pytest tests/ -v
# 41 tests passed
```

## 许可证

**CC BY-NC-SA 4.0** — 非商业用途可分享和改编，需署名。详见 [LICENSE](LICENSE)。

---

<div align="center">

Made with determination by [@Furinaaa-Cancan](https://github.com/Furinaaa-Cancan)

</div>
