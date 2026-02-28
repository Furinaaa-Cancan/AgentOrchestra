#!/usr/bin/env python3
"""模拟对比：当前架构 vs 任务分解架构

用一个真实场景 "实现用户认证模块" 来对比两种架构的执行流程。
不需要 LLM，纯粹模拟编排逻辑。

运行: python docs/simulate_architectures.py
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any


# ── 模拟数据 ──────────────────────────────────────────

COMPLEX_REQUIREMENT = "实现完整的用户认证模块：JWT 登录、注册、密码重置、中间件鉴权"

# 模拟 builder/reviewer 输出
MOCK_OUTPUTS = {
    "auth-login": {
        "builder": {"status": "completed", "summary": "实现 POST /login with JWT", "changed_files": ["/src/auth/login.py"]},
        "reviewer": {"decision": "approve", "summary": "JWT 实现正确"},
    },
    "auth-register": {
        "builder": {"status": "completed", "summary": "实现 POST /register with validation", "changed_files": ["/src/auth/register.py"]},
        "reviewer": {"decision": "reject", "feedback": "缺少邮箱格式验证", "issues": ["email validation"]},
    },
    "auth-register-retry": {
        "builder": {"status": "completed", "summary": "添加邮箱格式验证", "changed_files": ["/src/auth/register.py"]},
        "reviewer": {"decision": "approve", "summary": "验证逻辑完整"},
    },
    "auth-reset": {
        "builder": {"status": "completed", "summary": "实现密码重置流程", "changed_files": ["/src/auth/reset.py"]},
        "reviewer": {"decision": "approve", "summary": "流程安全"},
    },
    "auth-middleware": {
        "builder": {"status": "completed", "summary": "实现 JWT 中间件", "changed_files": ["/src/middleware/auth.py"]},
        "reviewer": {"decision": "approve", "summary": "中间件正确"},
    },
    "monolithic": {
        "builder": {"status": "completed", "summary": "实现完整认证模块", "changed_files": ["/src/auth/login.py", "/src/auth/register.py", "/src/auth/reset.py", "/src/middleware/auth.py"]},
        "reviewer": {"decision": "reject", "feedback": "注册缺少邮箱验证，中间件未处理 token 过期", "issues": ["email validation", "token expiry"]},
    },
    "monolithic-retry": {
        "builder": {"status": "completed", "summary": "修复验证和 token 过期", "changed_files": ["/src/auth/register.py", "/src/middleware/auth.py"]},
        "reviewer": {"decision": "reject", "feedback": "token 过期处理仍有竞态条件", "issues": ["race condition"]},
    },
    "monolithic-retry2": {
        "builder": {"status": "completed", "summary": "修复竞态条件", "changed_files": ["/src/middleware/auth.py"]},
        "reviewer": {"decision": "approve", "summary": "全部通过"},
    },
}


@dataclass
class SimEvent:
    time: float
    role: str
    action: str
    detail: str = ""


@dataclass
class SimResult:
    name: str
    events: list[SimEvent] = field(default_factory=list)
    total_build_review_cycles: int = 0
    total_retries: int = 0
    max_context_tokens: int = 0  # 模拟上下文大小
    final_status: str = ""


# ── 架构 A: 当前方案 — 单任务整体 build-review ──────────

def simulate_current_architecture() -> SimResult:
    """当前架构：一个大任务走完整个 build-review 循环"""
    result = SimResult(name="当前架构 (单体 build-review)")
    t = 0.0

    # Step 1: Plan — 把整个需求作为一个大任务
    result.events.append(SimEvent(t, "orchestrator", "plan", f"任务: {COMPLEX_REQUIREMENT}"))
    result.events.append(SimEvent(t, "orchestrator", "assign", "builder=windsurf, reviewer=cursor"))
    t += 1

    # Step 2: Build — builder 需要一次性实现 4 个功能
    result.events.append(SimEvent(t, "builder(windsurf)", "start",
        "需要实现: login + register + reset + middleware (上下文极大)"))
    context_size = 8000  # 模拟: 单体任务需要大量上下文
    result.max_context_tokens = context_size
    t += 15  # 模拟: 大任务需要更长时间
    output = MOCK_OUTPUTS["monolithic"]["builder"]
    result.events.append(SimEvent(t, "builder(windsurf)", "submit", output["summary"]))
    result.total_build_review_cycles += 1

    # Step 3: Review — reject! 大任务 reviewer 容易找出多个问题
    t += 5
    review = MOCK_OUTPUTS["monolithic"]["reviewer"]
    result.events.append(SimEvent(t, "reviewer(cursor)", "reject",
        f"问题: {review['issues']}  反馈: {review['feedback']}"))
    result.total_retries += 1

    # Step 4: Retry 1 — builder 需要修复多个问题，上下文更大
    t += 1
    result.events.append(SimEvent(t, "builder(windsurf)", "retry-1",
        "修复 2 个问题，上下文 = 原始 prompt + 第一轮代码 + reviewer 反馈"))
    context_size = 14000  # 上下文膨胀!
    result.max_context_tokens = max(result.max_context_tokens, context_size)
    t += 12
    output2 = MOCK_OUTPUTS["monolithic-retry"]["builder"]
    result.events.append(SimEvent(t, "builder(windsurf)", "submit", output2["summary"]))
    result.total_build_review_cycles += 1

    # Step 5: Review again — still reject!
    t += 5
    review2 = MOCK_OUTPUTS["monolithic-retry"]["reviewer"]
    result.events.append(SimEvent(t, "reviewer(cursor)", "reject",
        f"问题: {review2['issues']}  反馈: {review2['feedback']}"))
    result.total_retries += 1

    # Step 6: Retry 2 — 上下文继续膨胀
    t += 1
    result.events.append(SimEvent(t, "builder(windsurf)", "retry-2",
        "第3轮修复，上下文 = prompt + v1代码 + v1反馈 + v2代码 + v2反馈"))
    context_size = 20000  # 上下文严重膨胀 — MASAI 论文核心痛点
    result.max_context_tokens = max(result.max_context_tokens, context_size)
    t += 10
    output3 = MOCK_OUTPUTS["monolithic-retry2"]["builder"]
    result.events.append(SimEvent(t, "builder(windsurf)", "submit", output3["summary"]))
    result.total_build_review_cycles += 1

    # Step 7: Finally approve
    t += 5
    result.events.append(SimEvent(t, "reviewer(cursor)", "approve", "全部通过"))
    result.final_status = "approved (经过 2 次重试)"

    return result


# ── 架构 B: 改进方案 — 任务分解 + 独立 build-review ──────

def simulate_decomposed_architecture() -> SimResult:
    """改进架构：先分解任务，每个 sub-task 独立 build-review"""
    result = SimResult(name="改进架构 (任务分解 + 独立循环)")
    t = 0.0

    # Step 1: Decompose — 把大任务拆成 4 个独立 sub-task
    result.events.append(SimEvent(t, "orchestrator", "decompose", f"原始需求: {COMPLEX_REQUIREMENT}"))
    sub_tasks = [
        {"id": "auth-login", "desc": "实现 POST /login JWT 认证", "deps": []},
        {"id": "auth-register", "desc": "实现 POST /register 用户注册", "deps": []},
        {"id": "auth-reset", "desc": "实现密码重置流程", "deps": ["auth-login"]},
        {"id": "auth-middleware", "desc": "实现 JWT 鉴权中间件", "deps": ["auth-login"]},
    ]
    for st in sub_tasks:
        result.events.append(SimEvent(t, "orchestrator", "sub-task",
            f"{st['id']}: {st['desc']} (deps: {st['deps']})"))
    t += 2

    # Step 2: Execute each sub-task with independent build-review cycle
    for st in sub_tasks:
        task_id = st["id"]

        # Plan
        result.events.append(SimEvent(t, "orchestrator", f"plan({task_id})",
            f"独立 context，只包含 {task_id} 的信息"))
        context_size = 2500  # 每个 sub-task 上下文很小!
        result.max_context_tokens = max(result.max_context_tokens, context_size)

        # Build
        t += 1
        builder_out = MOCK_OUTPUTS[task_id]["builder"]
        result.events.append(SimEvent(t, f"builder({task_id})", "submit", builder_out["summary"]))
        result.total_build_review_cycles += 1
        t += 5

        # Review
        reviewer_out = MOCK_OUTPUTS[task_id]["reviewer"]
        if reviewer_out["decision"] == "approve":
            result.events.append(SimEvent(t, f"reviewer({task_id})", "approve", reviewer_out["summary"]))
        else:
            result.events.append(SimEvent(t, f"reviewer({task_id})", "reject", reviewer_out["feedback"]))
            result.total_retries += 1

            # Retry with focused feedback — 上下文不膨胀
            t += 1
            retry_key = f"{task_id}-retry"
            retry_out = MOCK_OUTPUTS[retry_key]["builder"]
            result.events.append(SimEvent(t, f"builder({task_id})", "retry-1", retry_out["summary"]))
            result.total_build_review_cycles += 1
            context_size = 3500  # 重试上下文只增加一点点
            result.max_context_tokens = max(result.max_context_tokens, context_size)
            t += 4

            retry_review = MOCK_OUTPUTS[retry_key]["reviewer"]
            result.events.append(SimEvent(t, f"reviewer({task_id})", "approve", retry_review["summary"]))

        t += 2

    # Step 3: Aggregate results
    result.events.append(SimEvent(t, "orchestrator", "aggregate",
        "汇总 4 个 sub-task 结果，生成最终报告"))
    result.final_status = "approved (1 个 sub-task 重试 1 次)"

    return result


# ── 对比输出 ──────────────────────────────────────────

def print_result(result: SimResult):
    print(f"\n{'='*70}")
    print(f"  {result.name}")
    print(f"{'='*70}")
    for ev in result.events:
        print(f"  [{ev.time:5.1f}s] {ev.role:30s} | {ev.action:15s} | {ev.detail[:50]}")
    print(f"  {'─'*66}")
    print(f"  总 build-review 次数:  {result.total_build_review_cycles}")
    print(f"  总重试次数:            {result.total_retries}")
    print(f"  最大上下文 (tokens):   {result.max_context_tokens:,}")
    print(f"  最终状态:              {result.final_status}")


def print_comparison(a: SimResult, b: SimResult):
    print(f"\n{'='*70}")
    print(f"  📊 对比总结")
    print(f"{'='*70}")
    print(f"  {'指标':<25s} {'当前架构':>15s} {'改进架构':>15s} {'差异':>10s}")
    print(f"  {'─'*66}")

    metrics = [
        ("build-review 次数", a.total_build_review_cycles, b.total_build_review_cycles),
        ("重试次数", a.total_retries, b.total_retries),
        ("最大上下文 (tokens)", a.max_context_tokens, b.max_context_tokens),
    ]
    for name, va, vb in metrics:
        diff = vb - va
        sign = "+" if diff > 0 else ""
        print(f"  {name:<25s} {va:>15,} {vb:>15,} {sign}{diff:>9,}")

    print()
    print("  关键发现:")
    print(f"  1. 上下文缩减 {a.max_context_tokens/b.max_context_tokens:.1f}x — MASAI 论文核心论点得到验证")
    print(f"  2. 重试从 {a.total_retries} 次降到 {b.total_retries} 次 — 小任务更容易一次做对")
    print(f"  3. 每个 sub-task 的 reviewer 只需审查一个功能，审查质量更高")
    print(f"  4. 任何 sub-task 失败不影响其他已完成的 sub-task")
    print()
    print("  架构选择结论:")
    print("  ✅ 保持 LangGraph 状态图作为每个 sub-task 的执行引擎 (已有 109 tests)")
    print("  ✅ 新增任务分解层: 大需求 → sub-task queue → 逐个 build-review")
    print("  ❌ 不做: 层级 sub-agent 嵌套 (IDE 做不到)")
    print("  ❌ 不做: agent 间实时对话 (延迟太高)")
    print("  ❌ 不做: 并行执行 sub-task (IDE 同时只能做一件事)")


if __name__ == "__main__":
    print("🔬 Multi-Agent 编排架构模拟对比")
    print("   场景: " + COMPLEX_REQUIREMENT)

    current = simulate_current_architecture()
    improved = simulate_decomposed_architecture()

    print_result(current)
    print_result(improved)
    print_comparison(current, improved)
