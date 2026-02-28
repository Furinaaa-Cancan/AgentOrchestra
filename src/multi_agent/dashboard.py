"""Goal Dashboard generator — produces .multi-agent/dashboard.md."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from multi_agent.config import dashboard_path


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def generate_dashboard(
    task_id: str,
    done_criteria: list[str],
    current_agent: str,
    current_role: str,
    conversation: list[dict],
    status_msg: str = "",
    timeout_remaining: str = "",
    error: str | None = None,
) -> str:
    """Generate markdown dashboard content."""
    lines: list[str] = []
    lines.append(f"# 🎯 {task_id}\n")

    # Progress section
    lines.append("## 进度\n")
    lines.append("| 目标 | 状态 |")
    lines.append("|------|------|")
    for criterion in done_criteria:
        lines.append(f"| {criterion} | ⬜ 待验证 |")
    lines.append("")

    # Current status
    lines.append("## 当前状态\n")
    if error:
        lines.append(f"❌ **错误**: {error}\n")
    elif status_msg:
        lines.append(f"{status_msg}\n")
    else:
        emoji = "🔵" if current_role == "builder" else "🟡"
        action = "执行 builder 任务" if current_role == "builder" else "执行审查"
        lines.append(f"{emoji} **{current_agent}** 正在{action}")
        lines.append(f"📄 Prompt: `.multi-agent/inbox/{current_role}.md`")
        if timeout_remaining:
            lines.append(f"⏱️ 剩余时间: {timeout_remaining}")
    lines.append("")

    # Conversation history
    lines.append("## 对话历史\n")
    lines.append("| 时间 | 角色 | 动作 |")
    lines.append("|------|------|------|")
    for entry in conversation:
        role = entry.get("role", "?")
        action = entry.get("action", entry.get("decision", entry.get("output", "—")))
        lines.append(f"| {_now()} | {role} | {action} |")
    lines.append("")

    # Actions
    lines.append("## 操作\n")
    lines.append(f"- 查看 prompt: `cat .multi-agent/inbox/{current_role}.md`")
    lines.append("- 手动提交: `ma done`")
    lines.append("- 查看状态: `ma status`")
    lines.append("- 取消任务: `ma cancel`")
    lines.append("")

    return "\n".join(lines)


def write_dashboard(
    task_id: str,
    done_criteria: list[str],
    current_agent: str,
    current_role: str,
    conversation: list[dict],
    status_msg: str = "",
    timeout_remaining: str = "",
    error: str | None = None,
    path: Path | None = None,
) -> Path:
    """Write dashboard markdown to disk."""
    content = generate_dashboard(
        task_id=task_id,
        done_criteria=done_criteria,
        current_agent=current_agent,
        current_role=current_role,
        conversation=conversation,
        status_msg=status_msg,
        timeout_remaining=timeout_remaining,
        error=error,
    )
    p = path or dashboard_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p
