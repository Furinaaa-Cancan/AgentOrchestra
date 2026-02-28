"""Unified configuration — resolve all paths relative to project root."""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

import yaml


def _find_root() -> Path:
    """Walk up from CWD (or env override) looking for the project marker."""
    override = os.environ.get("MA_ROOT")
    if override:
        return Path(override).resolve()

    cur = Path.cwd()
    for parent in [cur, *cur.parents]:
        if (parent / "skills").is_dir() and (parent / "agents").is_dir():
            return parent
    return cur


@lru_cache(maxsize=1)
def root_dir() -> Path:
    return _find_root()


def workspace_dir() -> Path:
    return root_dir() / ".multi-agent"


def skills_dir() -> Path:
    return root_dir() / "skills"


def agents_profile_path() -> Path:
    return root_dir() / "agents" / "profiles.json"


def workmode_path() -> Path:
    return root_dir() / "config" / "workmode.yaml"


def store_db_path() -> Path:
    return workspace_dir() / "store.db"


def inbox_dir() -> Path:
    return workspace_dir() / "inbox"


def outbox_dir() -> Path:
    return workspace_dir() / "outbox"


def tasks_dir() -> Path:
    return workspace_dir() / "tasks"


def history_dir() -> Path:
    return workspace_dir() / "history"


def dashboard_path() -> Path:
    return workspace_dir() / "dashboard.md"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
