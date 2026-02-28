"""Workspace manager — manages .multi-agent/ directory (inbox/outbox/dashboard)."""

from __future__ import annotations

import json
from pathlib import Path

from multi_agent.config import (
    workspace_dir,
    inbox_dir,
    outbox_dir,
    tasks_dir,
    history_dir,
)


def ensure_workspace() -> Path:
    """Create .multi-agent/ and all subdirectories if they don't exist."""
    ws = workspace_dir()
    for d in [ws, inbox_dir(), outbox_dir(), tasks_dir(), history_dir()]:
        d.mkdir(parents=True, exist_ok=True)
    return ws


def write_inbox(agent_id: str, content: str) -> Path:
    """Write a prompt file to inbox/{agent_id}.md."""
    ensure_workspace()
    path = inbox_dir() / f"{agent_id}.md"
    path.write_text(content, encoding="utf-8")
    return path


def read_outbox(agent_id: str) -> dict | None:
    """Read and parse outbox/{agent_id}.json. Returns None if not found or corrupt."""
    path = outbox_dir() / f"{agent_id}.json"
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def write_outbox(agent_id: str, data: dict) -> Path:
    """Write agent output to outbox/{agent_id}.json."""
    ensure_workspace()
    path = outbox_dir() / f"{agent_id}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


def clear_outbox(agent_id: str) -> None:
    """Remove outbox file for an agent (before a new cycle)."""
    path = outbox_dir() / f"{agent_id}.json"
    if path.exists():
        path.unlink()


def clear_inbox(agent_id: str) -> None:
    """Remove inbox file for an agent."""
    path = inbox_dir() / f"{agent_id}.md"
    if path.exists():
        path.unlink()


def save_task_yaml(task_id: str, data: dict) -> Path:
    """Save task state to tasks/{task_id}.yaml."""
    import yaml

    ensure_workspace()
    path = tasks_dir() / f"{task_id}.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    return path


def archive_conversation(task_id: str, conversation: list[dict]) -> Path:
    """Archive conversation history to history/{task_id}.json."""
    ensure_workspace()
    path = history_dir() / f"{task_id}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(conversation, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path
