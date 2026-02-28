"""Tests for workspace manager."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from multi_agent import workspace


@pytest.fixture
def tmp_workspace(tmp_path):
    """Patch workspace dirs to use a temp directory."""
    ws = tmp_path / ".multi-agent"
    with patch("multi_agent.workspace.workspace_dir", return_value=ws), \
         patch("multi_agent.workspace.inbox_dir", return_value=ws / "inbox"), \
         patch("multi_agent.workspace.outbox_dir", return_value=ws / "outbox"), \
         patch("multi_agent.workspace.tasks_dir", return_value=ws / "tasks"), \
         patch("multi_agent.workspace.history_dir", return_value=ws / "history"):
        yield ws


class TestEnsureWorkspace:
    def test_creates_dirs(self, tmp_workspace):
        workspace.ensure_workspace()
        assert (tmp_workspace / "inbox").is_dir()
        assert (tmp_workspace / "outbox").is_dir()
        assert (tmp_workspace / "tasks").is_dir()
        assert (tmp_workspace / "history").is_dir()

    def test_idempotent(self, tmp_workspace):
        workspace.ensure_workspace()
        workspace.ensure_workspace()
        assert (tmp_workspace / "inbox").is_dir()


class TestInboxOutbox:
    def test_write_read_inbox(self, tmp_workspace):
        workspace.ensure_workspace()
        path = workspace.write_inbox("windsurf", "# Hello Builder")
        assert path.exists()
        assert path.read_text(encoding="utf-8") == "# Hello Builder"

    def test_write_read_outbox(self, tmp_workspace):
        workspace.ensure_workspace()
        data = {"status": "completed", "summary": "done"}
        workspace.write_outbox("windsurf", data)
        result = workspace.read_outbox("windsurf")
        assert result["status"] == "completed"

    def test_read_outbox_missing(self, tmp_workspace):
        workspace.ensure_workspace()
        assert workspace.read_outbox("nonexistent") is None

    def test_clear_outbox(self, tmp_workspace):
        workspace.ensure_workspace()
        workspace.write_outbox("windsurf", {"status": "done"})
        workspace.clear_outbox("windsurf")
        assert workspace.read_outbox("windsurf") is None

    def test_clear_inbox(self, tmp_workspace):
        workspace.ensure_workspace()
        path = workspace.write_inbox("windsurf", "prompt")
        assert path.exists()
        workspace.clear_inbox("windsurf")
        assert not path.exists()


class TestArchive:
    def test_archive_conversation(self, tmp_workspace):
        workspace.ensure_workspace()
        convo = [{"role": "orchestrator", "action": "assigned"}]
        path = workspace.archive_conversation("task-123", convo)
        assert path.exists()
        with path.open() as f:
            loaded = json.load(f)
        assert loaded == convo
