"""Unit tests for cli.py helper functions — _log_error_to_file, _mark_task_inactive,
_is_task_terminal_or_missing, _read_done_output, _auto_fix_runtime_consistency."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# ── _log_error_to_file ───────────────────────────────────


class TestLogErrorToFile:
    def test_writes_log_file(self, tmp_path, monkeypatch):
        from multi_agent.cli import _log_error_to_file
        with patch("multi_agent.config.workspace_dir", return_value=tmp_path):
            _log_error_to_file("test_cmd", ValueError("boom"))
        logs = list((tmp_path / "logs").glob("error-*.log"))
        assert len(logs) == 1
        content = logs[0].read_text()
        assert "test_cmd" in content
        assert "boom" in content

    def test_suppresses_errors(self, tmp_path):
        from multi_agent.cli import _log_error_to_file
        # If workspace_dir raises, should not propagate
        with patch("multi_agent.config.workspace_dir", side_effect=RuntimeError):
            _log_error_to_file("cmd", ValueError("x"))  # should not raise


# ── _mark_task_inactive ──────────────────────────────────


class TestMarkTaskInactive:
    def test_marks_existing_task(self, tmp_path, monkeypatch):
        from multi_agent.cli import _mark_task_inactive
        tasks = tmp_path / "tasks"
        tasks.mkdir()
        tf = tasks / "task-001.yaml"
        tf.write_text(yaml.dump({"task_id": "task-001", "status": "active"}), encoding="utf-8")
        with patch("multi_agent.config.tasks_dir", return_value=tasks):
            result = _mark_task_inactive("task-001", status="cancelled", reason="user request")
        assert result is True
        data = yaml.safe_load(tf.read_text())
        assert data["status"] == "cancelled"
        assert data["reason"] == "user request"

    def test_returns_false_for_missing_file(self, tmp_path):
        from multi_agent.cli import _mark_task_inactive
        tasks = tmp_path / "tasks"
        tasks.mkdir()
        with patch("multi_agent.config.tasks_dir", return_value=tasks):
            assert _mark_task_inactive("nonexistent", status="x", reason="y") is False

    def test_returns_false_for_non_dict(self, tmp_path):
        from multi_agent.cli import _mark_task_inactive
        tasks = tmp_path / "tasks"
        tasks.mkdir()
        tf = tasks / "task-002.yaml"
        tf.write_text("- a list\n- not a dict\n", encoding="utf-8")
        with patch("multi_agent.config.tasks_dir", return_value=tasks):
            assert _mark_task_inactive("task-002", status="x", reason="y") is False


# ── _is_task_terminal_or_missing ─────────────────────────


class TestIsTaskTerminalOrMissing:
    def test_terminal_task(self):
        from multi_agent.cli import _is_task_terminal_or_missing
        app = MagicMock()
        snapshot = MagicMock()
        snapshot.values = {"final_status": "approved"}
        snapshot.next = []
        app.get_state.return_value = snapshot
        assert _is_task_terminal_or_missing(app, "t-1") is True

    def test_active_task(self):
        from multi_agent.cli import _is_task_terminal_or_missing
        app = MagicMock()
        snapshot = MagicMock()
        snapshot.values = {}
        snapshot.next = ["build_node"]
        app.get_state.return_value = snapshot
        assert _is_task_terminal_or_missing(app, "t-1") is False

    def test_no_snapshot(self):
        from multi_agent.cli import _is_task_terminal_or_missing
        app = MagicMock()
        app.get_state.return_value = None
        assert _is_task_terminal_or_missing(app, "t-1") is True

    def test_exception_returns_false(self):
        from multi_agent.cli import _is_task_terminal_or_missing
        app = MagicMock()
        app.get_state.side_effect = RuntimeError("db error")
        assert _is_task_terminal_or_missing(app, "t-1") is False

    def test_no_next_is_terminal(self):
        from multi_agent.cli import _is_task_terminal_or_missing
        app = MagicMock()
        snapshot = MagicMock()
        snapshot.values = {}
        snapshot.next = []
        app.get_state.return_value = snapshot
        assert _is_task_terminal_or_missing(app, "t-1") is True


# ── _read_done_output ────────────────────────────────────


class TestReadDoneOutput:
    def test_reads_from_file(self, tmp_path):
        from multi_agent.cli import _read_done_output
        f = tmp_path / "output.json"
        f.write_text(json.dumps({"status": "completed", "summary": "ok"}), encoding="utf-8")
        result = _read_done_output("builder", str(f))
        assert result["status"] == "completed"

    def test_file_too_large_exits(self, tmp_path):
        from multi_agent.cli import _read_done_output
        f = tmp_path / "big.json"
        f.write_text("x" * (11 * 1024 * 1024), encoding="utf-8")
        with pytest.raises(SystemExit):
            _read_done_output("builder", str(f))

    def test_invalid_json_file_exits(self, tmp_path):
        from multi_agent.cli import _read_done_output
        f = tmp_path / "bad.json"
        f.write_text("not json", encoding="utf-8")
        with pytest.raises(SystemExit):
            _read_done_output("builder", str(f))

    def test_reads_from_outbox(self):
        from multi_agent.cli import _read_done_output
        with patch("multi_agent.cli.read_outbox", return_value={"decision": "approve"}):
            result = _read_done_output("reviewer", None)
        assert result["decision"] == "approve"

    def test_stdin_fallback(self, monkeypatch):
        from multi_agent.cli import _read_done_output
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO('{"status": "done"}'))
        with patch("multi_agent.cli.read_outbox", return_value=None):
            result = _read_done_output("builder", None)
        assert result["status"] == "done"

    def test_stdin_invalid_json_exits(self, monkeypatch):
        from multi_agent.cli import _read_done_output
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO("not json"))
        with patch("multi_agent.cli.read_outbox", return_value=None), \
             pytest.raises(SystemExit):
            _read_done_output("builder", None)

    def test_no_output_anywhere_exits(self, monkeypatch):
        from multi_agent.cli import _read_done_output
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO(""))
        with patch("multi_agent.cli.read_outbox", return_value=None), \
             pytest.raises(SystemExit):
            _read_done_output("builder", None)

    def test_file_stat_error_treated_as_zero(self, tmp_path):
        from multi_agent.cli import _read_done_output
        f = tmp_path / "output.json"
        f.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        with patch.object(Path, "stat", side_effect=OSError("perm denied")):
            result = _read_done_output("builder", str(f))
        assert result["status"] == "ok"


# ── _auto_fix_runtime_consistency ────────────────────────


class TestAutoFixRuntimeConsistency:
    def test_no_active_no_lock(self):
        from multi_agent.cli import _auto_fix_runtime_consistency
        with patch("multi_agent.cli._detect_active_task", return_value=None), \
             patch("multi_agent.cli.read_lock", return_value=None):
            actions = _auto_fix_runtime_consistency()
        assert actions == []

    def test_active_no_lock_terminal(self):
        from multi_agent.cli import _auto_fix_runtime_consistency
        with patch("multi_agent.cli._detect_active_task", return_value="task-001"), \
             patch("multi_agent.cli.read_lock", return_value=None), \
             patch("multi_agent.graph.compile_graph"), \
             patch("multi_agent.cli._is_task_terminal_or_missing", return_value=True), \
             patch("multi_agent.cli._mark_task_inactive", return_value=True):
            actions = _auto_fix_runtime_consistency()
        assert any("陈旧" in a for a in actions)

    def test_active_no_lock_restores(self):
        from multi_agent.cli import _auto_fix_runtime_consistency
        with patch("multi_agent.cli._detect_active_task", return_value="task-001"), \
             patch("multi_agent.cli.read_lock", return_value=None), \
             patch("multi_agent.graph.compile_graph"), \
             patch("multi_agent.cli._is_task_terminal_or_missing", return_value=False), \
             patch("multi_agent.cli.acquire_lock"):
            actions = _auto_fix_runtime_consistency()
        assert any("恢复锁" in a for a in actions)

    def test_lock_no_active_terminal_releases(self):
        from multi_agent.cli import _auto_fix_runtime_consistency
        with patch("multi_agent.cli._detect_active_task", return_value=None), \
             patch("multi_agent.cli.read_lock", return_value="task-001"), \
             patch("multi_agent.graph.compile_graph"), \
             patch("multi_agent.cli._is_task_terminal_or_missing", return_value=True), \
             patch("multi_agent.cli.release_lock"):
            actions = _auto_fix_runtime_consistency()
        assert any("释放孤立锁" in a for a in actions)

    def test_lock_no_active_still_running_keeps(self):
        from multi_agent.cli import _auto_fix_runtime_consistency
        with patch("multi_agent.cli._detect_active_task", return_value=None), \
             patch("multi_agent.cli.read_lock", return_value="task-001"), \
             patch("multi_agent.graph.compile_graph"), \
             patch("multi_agent.cli._is_task_terminal_or_missing", return_value=False):
            actions = _auto_fix_runtime_consistency()
        assert any("保留锁" in a for a in actions)

    def test_lock_mismatch_realigns(self):
        from multi_agent.cli import _auto_fix_runtime_consistency
        with patch("multi_agent.cli._detect_active_task", return_value="task-002"), \
             patch("multi_agent.cli.read_lock", return_value="task-001"), \
             patch("multi_agent.graph.compile_graph"), \
             patch("multi_agent.cli.release_lock"), \
             patch("multi_agent.cli.acquire_lock"):
            actions = _auto_fix_runtime_consistency()
        assert any("重对齐" in a for a in actions)


# ── _sigterm_handler ─────────────────────────────────────


class TestSigtermHandler:
    def test_handler_raises_systemexit(self):
        import signal

        from multi_agent.cli import _sigterm_handler
        with patch("multi_agent.cli.read_lock", return_value="task-1"), \
             patch("multi_agent.cli.release_lock"), \
             patch("multi_agent.cli.clear_runtime"), \
             pytest.raises(SystemExit) as exc_info:
            _sigterm_handler(signal.SIGTERM, None)
        assert exc_info.value.code == 128 + signal.SIGTERM

    def test_handler_no_lock(self):
        import signal

        from multi_agent.cli import _sigterm_handler
        with patch("multi_agent.cli.read_lock", return_value=None), \
             patch("multi_agent.cli.release_lock") as mock_rel, \
             patch("multi_agent.cli.clear_runtime"), \
             pytest.raises(SystemExit):
            _sigterm_handler(signal.SIGTERM, None)
        mock_rel.assert_not_called()
