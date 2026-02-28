<div align="center">

# AgentOrchestra

**IDE-Agnostic Multi-Agent Orchestration Framework**

*One command to coordinate any combination of AI coding assistants — Windsurf, Cursor, Codex, Kiro, Copilot, and more*

[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-56%20passed-brightgreen.svg)]()

[English](#english) | [中文](#中文)

</div>

---

<a id="english"></a>

## 30-Second Demo

```bash
$ ma go "Add input validation" --builder windsurf --reviewer cursor

🚀 Task: task-a1b2c3d4
   Requirement: Add input validation

📋 在 windsurf IDE 里对 AI 说:
   "帮我完成 @.multi-agent/TASK.md 里的任务"

👁️  Auto-watching outbox/ (Ctrl-C to stop)

[00:32] 📥 builder (windsurf) submitted! Advancing...
[00:32] 📋 在 cursor IDE 里对 AI 说:
             "帮我完成 @.multi-agent/TASK.md 里的任务"
[01:15] 📥 reviewer (cursor) submitted! Advancing...
[01:17] ✅ Task finished — approved
```

**That's it.** One terminal command. Tell each IDE AI one sentence. The terminal handles the rest.

## What is AgentOrchestra?

AgentOrchestra coordinates multiple IDE-based AI coding assistants through a **Plan → Build → Review → Decide** cycle. One AI implements, a different AI reviews. Cross-model adversarial review catches mistakes that self-review misses.

### Why?

AI coding assistants are powerful individually, but:
- They never review their own blind spots
- Coordinating two IDEs manually is tedious (copy prompts, track turns, pass feedback)
- No persistent state across sessions

### How it works

```
Terminal                    IDE A (builder)              IDE B (reviewer)
   │                            │                            │
   │  ma go "requirement"       │                            │
   │──────────────────────►     │                            │
   │  writes TASK.md            │                            │
   │                            │                            │
   │                       @TASK.md                          │
   │                       reads prompt                      │
   │                       does the work                     │
   │                       saves outbox/builder.json         │
   │  ◄─── auto-detects ───────┘                            │
   │                                                         │
   │  rewrites TASK.md for reviewer                          │
   │                                                    @TASK.md
   │                                                    reads prompt
   │                                                    reviews code
   │                                                    saves outbox/reviewer.json
   │  ◄─── auto-detects ────────────────────────────────────┘
   │
   │  ✅ approved (or retry with feedback)
```

**Key insight**: `TASK.md` is self-contained. It embeds the full prompt — the IDE AI gets everything from one `@file` reference, no jumping between files.

## Quick Start

### Install

```bash
git clone https://github.com/Furinaaa-Cancan/AgentOrchestra.git
cd AgentOrchestra
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Configure IDEs

Edit `agents/agents.yaml`:

```yaml
agents:
  - id: windsurf
    capabilities: [planning, implementation, testing, docs]
  - id: cursor
    capabilities: [planning, implementation, testing, review, docs]
  # Add any IDE here

defaults:
  builder: windsurf
  reviewer: cursor
```

### Use

```bash
# One command — starts task + auto-watches for output
ma go "Implement POST /users endpoint" --builder windsurf --reviewer cursor

# Then in each IDE, just say:
# "帮我完成 @.multi-agent/TASK.md 里的任务"
```

The terminal auto-detects when the IDE AI saves its output and advances the workflow. No `ma done` needed.

### Supported IDEs

Any IDE with an AI assistant. Tested with: **Windsurf**, **Cursor**, **Codex**, **Kiro**, **Antigravity**, **Copilot**, **Aider**, **Cline**. Add any other in `agents.yaml`.

## Architecture

### 4-Node LangGraph Cycle

```
               ┌─────────┐
               │  START   │
               └────┬────┘
                    │
               ┌────▼────┐
          ┌───▶│  plan   │  Resolve roles, render prompt into TASK.md
          │    └────┬────┘
          │         │
          │    ┌────▼────┐
          │    │  build  │  interrupt() — IDE AI reads TASK.md, saves outbox
          │    └────┬────┘
          │         │ (validate output, check quality gates)
          │    ┌────▼────┐
          │    │ review  │  interrupt() — reviewer IDE reads TASK.md, saves outbox
          │    └────┬────┘
          │         │
          │    ┌────▼────┐
          │    │ decide  │  approve → END, reject → retry with feedback
          │    └────┬────┘
          │         │
          └─────────┘
```

### Workspace

```
.multi-agent/
├── TASK.md             ← Self-contained prompt (THE file IDEs read)
├── inbox/
│   ├── builder.md      ← Builder prompt source (embedded into TASK.md)
│   └── reviewer.md     ← Reviewer prompt source (embedded into TASK.md)
├── outbox/
│   ├── builder.json    ← Builder writes here → auto-detected
│   └── reviewer.json   ← Reviewer writes here → auto-detected
├── dashboard.md        ← Progress panel
├── tasks/              ← Task state markers (active/completed/failed)
├── history/            ← Conversation archive
└── store.db            ← LangGraph SQLite checkpoint
```

### CLI Reference

| Command | Description |
|---------|-------------|
| `ma go "requirement"` | Start task + auto-watch (default) |
| `ma go "req" --builder X --reviewer Y` | Specify IDEs |
| `ma go "req" --no-watch` | Start without auto-watch |
| `ma watch` | Resume watching (after `--no-watch`) |
| `ma done` | Manually submit output |
| `ma done --file output.json` | Submit from specific file |
| `ma status` | Show current task state |
| `ma cancel` | Cancel active task |

## Research Foundation

| Paper | Venue | Design Principle Applied |
|-------|-------|------------------------|
| Evolving Orchestration | **NeurIPS 2025** | Compact cyclic graph (4 nodes) outperforms complex DAGs |
| ChatDev | **ACL 2024** | One requirement in → fully automated role-pair chain |
| MetaGPT | **ICLR 2024** | Publish-subscribe artifacts (outbox auto-detection) |
| MASAI | **ICSE 2025** | Modular sub-agents with well-defined objectives per role |
| HULA | **ICSE 2025** | Minimal-friction human-in-the-loop (one sentence per IDE) |
| SWE-agent | **ICLR 2025** | Agent-Computer Interface design (TASK.md as ACI) |
| Agentless | **FSE 2025** | Simple pipeline beats over-engineered agents |
| MapCoder | **ACL 2024** | Verification stage as separate agent (reviewer role) |

### Key Design Decisions

| Decision | Rationale | Paper |
|----------|-----------|-------|
| Self-contained TASK.md | IDE AI needs ONE file reference, not multi-hop | SWE-agent ACI |
| Auto-watch outbox | Zero manual `ma done` in normal flow | MetaGPT publish-subscribe |
| Builder ≠ Reviewer | Cross-model adversarial review catches self-review blind spots | ChatDev role pairs |
| 4 graph nodes | RL-trained orchestrators converge to compact cycles | Evolving Orchestration |
| File-based communication | Works with any IDE, zero integration needed | HULA minimal friction |
| Retry with reviewer feedback | Reviewer rejection injects concrete feedback into next attempt | MapCoder verification |

## Running Tests

```bash
pytest tests/ -v
# 56 tests passed
```

## License

**CC BY-NC-SA 4.0** — Non-commercial use with attribution. See [LICENSE](LICENSE).

---

<a id="中文"></a>

<div align="center">

# AgentOrchestra

**IDE 无关的多智能体编排框架**

*一个命令协调任意 AI 编程助手组合*

</div>

## 30 秒演示

```bash
$ ma go "添加输入校验" --builder windsurf --reviewer cursor

🚀 Task: task-a1b2c3d4
   Requirement: 添加输入校验

📋 在 windsurf IDE 里对 AI 说:
   "帮我完成 @.multi-agent/TASK.md 里的任务"

👁️  Auto-watching outbox/ (Ctrl-C to stop)

[00:32] 📥 builder (windsurf) submitted! Advancing...
[00:32] 📋 在 cursor IDE 里对 AI 说:
             "帮我完成 @.multi-agent/TASK.md 里的任务"
[01:15] 📥 reviewer (cursor) submitted! Advancing...
[01:17] ✅ Task finished — approved
```

**一个终端命令。在每个 IDE 里说一句话。终端自动推进。**

## 这是什么？

AgentOrchestra 协调多个 IDE 的 AI 编程助手，通过 **Plan → Build → Review → Decide** 循环协作。一个 AI 实现，另一个 AI 审查。跨模型对抗审查能捕获自我审查的盲点。

### 为什么需要？

- AI 助手从不审查自己的盲点
- 手动协调两个 IDE 很麻烦（复制 prompt、追踪轮次、传递反馈）
- 会话间无持久化状态

### 工作原理

```
终端                        IDE A (builder)              IDE B (reviewer)
  │                              │                            │
  │  ma go "需求"                │                            │
  │──────────────────────►       │                            │
  │  写入 TASK.md                │                            │
  │                         @TASK.md                          │
  │                         读取完整 prompt                    │
  │                         执行开发工作                       │
  │                         保存 outbox/builder.json          │
  │  ◄─── 自动检测 ────────────┘                              │
  │                                                           │
  │  重写 TASK.md (reviewer prompt)                           │
  │                                                      @TASK.md
  │                                                      读取审查 prompt
  │                                                      审查代码
  │                                                      保存 outbox/reviewer.json
  │  ◄─── 自动检测 ──────────────────────────────────────────┘
  │
  │  ✅ 通过 (或带反馈重试)
```

**核心**: `TASK.md` 是自包含的完整 prompt。IDE AI 通过一次 `@file` 引用获取所有信息。

## 快速开始

### 安装

```bash
git clone https://github.com/Furinaaa-Cancan/AgentOrchestra.git
cd AgentOrchestra
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### 配置 IDE

编辑 `agents/agents.yaml`：

```yaml
agents:
  - id: windsurf
    capabilities: [planning, implementation, testing, docs]
  - id: cursor
    capabilities: [planning, implementation, testing, review, docs]
  # 添加任何 IDE

defaults:
  builder: windsurf
  reviewer: cursor
```

### 使用

```bash
# 一个命令 — 启动任务 + 自动监听输出
ma go "实现 POST /users endpoint" --builder windsurf --reviewer cursor

# 然后在每个 IDE 里说:
# "帮我完成 @.multi-agent/TASK.md 里的任务"
```

终端自动检测 IDE AI 的输出并推进流程。无需手动 `ma done`。

### CLI 命令

| 命令 | 说明 |
|------|------|
| `ma go "需求"` | 启动任务 + 自动监听 |
| `ma go "需求" --builder X --reviewer Y` | 指定 IDE |
| `ma go "需求" --no-watch` | 启动但不自动监听 |
| `ma watch` | 恢复监听 (`--no-watch` 后) |
| `ma done` | 手动提交输出 |
| `ma status` | 查看任务状态 |
| `ma cancel` | 取消任务 |

### 支持的 IDE

任何带 AI 助手的 IDE: **Windsurf**, **Cursor**, **Codex**, **Kiro**, **Antigravity**, **Copilot**, **Aider**, **Cline**。在 `agents.yaml` 中添加任意 IDE。

## 研究基础

| 论文 | 会议 | 应用的设计原则 |
|------|------|---------------|
| Evolving Orchestration | **NeurIPS 2025** | 4 节点紧凑循环优于复杂 DAG |
| ChatDev | **ACL 2024** | 一个需求输入 → 全自动角色链 |
| MetaGPT | **ICLR 2024** | 发布-订阅制品（outbox 自动检测） |
| MASAI | **ICSE 2025** | 模块化子代理，每角色有明确目标 |
| HULA | **ICSE 2025** | 最小摩擦人机交互（每 IDE 一句话） |
| SWE-agent | **ICLR 2025** | Agent-Computer Interface 设计（TASK.md 即 ACI） |
| Agentless | **FSE 2025** | 简单管道优于过度工程化的代理 |
| MapCoder | **ACL 2024** | 验证阶段作为独立代理（reviewer 角色） |

## 测试

```bash
pytest tests/ -v   # 56 tests passed
```

## 许可证

**CC BY-NC-SA 4.0** — 非商业用途，需署名。详见 [LICENSE](LICENSE)。

---

<div align="center">

Made with determination by [@Furinaaa-Cancan](https://github.com/Furinaaa-Cancan)

</div>
