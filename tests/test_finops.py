"""Tests for multi_agent.finops — FinOps token usage tracking and cost reporting."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def _isolate_workspace(tmp_path, monkeypatch):
    """Redirect workspace to a temp dir so tests don't pollute real workspace."""
    ws = tmp_path / ".multi-agent"
    ws.mkdir()
    monkeypatch.setenv("MA_ROOT", str(tmp_path))
    # Patch workspace_dir to return our tmp workspace
    monkeypatch.setattr("multi_agent.finops.workspace_dir", lambda: ws)
    return ws


class TestRecordTaskUsage:
    def test_creates_log_file(self, _isolate_workspace):
        from multi_agent.finops import record_task_usage

        record_task_usage(
            task_id="test-task-1",
            node="build",
            agent_id="codex",
            input_tokens=100,
            output_tokens=50,
        )

        log_path = _isolate_workspace / "logs" / "token-usage.jsonl"
        assert log_path.exists()
        entries = [json.loads(l) for l in log_path.read_text().strip().splitlines()]
        assert len(entries) == 1
        assert entries[0]["task_id"] == "test-task-1"
        assert entries[0]["node"] == "build"
        assert entries[0]["input_tokens"] == 100
        assert entries[0]["output_tokens"] == 50
        assert entries[0]["total_tokens"] == 150

    def test_appends_multiple_entries(self, _isolate_workspace):
        from multi_agent.finops import record_task_usage

        record_task_usage(task_id="t1", node="build", input_tokens=100, output_tokens=50)
        record_task_usage(task_id="t1", node="review", input_tokens=200, output_tokens=100)

        log_path = _isolate_workspace / "logs" / "token-usage.jsonl"
        entries = [json.loads(l) for l in log_path.read_text().strip().splitlines()]
        assert len(entries) == 2
        assert entries[0]["node"] == "build"
        assert entries[1]["node"] == "review"

    def test_records_cost_and_model(self, _isolate_workspace):
        from multi_agent.finops import record_task_usage

        record_task_usage(
            task_id="t2",
            node="build",
            input_tokens=1000,
            output_tokens=500,
            cost=0.0125,
            model="gpt-4o",
        )

        log_path = _isolate_workspace / "logs" / "token-usage.jsonl"
        entry = json.loads(log_path.read_text().strip())
        assert entry["cost"] == 0.0125
        assert entry["model"] == "gpt-4o"


class TestLoadUsageLog:
    def test_empty_when_no_file(self, _isolate_workspace):
        from multi_agent.finops import load_usage_log

        assert load_usage_log() == []

    def test_loads_entries(self, _isolate_workspace):
        from multi_agent.finops import load_usage_log, record_task_usage

        record_task_usage(task_id="t1", node="build", input_tokens=100, output_tokens=50)
        entries = load_usage_log()
        assert len(entries) == 1
        assert entries[0]["task_id"] == "t1"

    def test_rejects_oversized_file(self, _isolate_workspace):
        from multi_agent.finops import load_usage_log

        log_path = _isolate_workspace / "logs" / "token-usage.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # Write a file that exceeds size limit marker
        with mock.patch("multi_agent.finops._MAX_USAGE_FILE_SIZE", 100):
            log_path.write_text("x" * 200)
            assert load_usage_log() == []


class TestEstimateCost:
    def test_default_pricing(self):
        from multi_agent.finops import estimate_cost

        cost = estimate_cost(1_000_000, 500_000, model="default")
        # default: input 2.50/M + output 10.00/M = 2.50 + 5.00 = 7.50
        assert cost == 7.5

    def test_specific_model(self):
        from multi_agent.finops import estimate_cost

        cost = estimate_cost(1000, 500, model="gpt-4o-mini")
        # gpt-4o-mini: 0.15/M input + 0.60/M output
        expected = (1000 * 0.15 + 500 * 0.60) / 1_000_000
        assert abs(cost - expected) < 1e-6

    def test_unknown_model_uses_default(self):
        from multi_agent.finops import estimate_cost

        cost = estimate_cost(1000, 500, model="unknown-model-xyz")
        cost_default = estimate_cost(1000, 500, model="default")
        assert cost == cost_default


class TestAggregateUsage:
    def test_aggregate_empty(self, _isolate_workspace):
        from multi_agent.finops import aggregate_usage

        agg = aggregate_usage()
        assert agg["total_tokens"] == 0
        assert agg["task_count"] == 0

    def test_aggregate_with_data(self, _isolate_workspace):
        from multi_agent.finops import aggregate_usage, record_task_usage

        record_task_usage(task_id="t1", node="build", agent_id="codex", input_tokens=100, output_tokens=50, cost=0.01)
        record_task_usage(task_id="t1", node="review", agent_id="claude", input_tokens=200, output_tokens=100, cost=0.02)
        record_task_usage(task_id="t2", node="build", agent_id="codex", input_tokens=300, output_tokens=150, cost=0.03)

        agg = aggregate_usage()
        assert agg["total_tokens"] == 150 + 300 + 450
        assert agg["task_count"] == 2
        assert agg["entry_count"] == 3
        assert abs(agg["total_cost"] - 0.06) < 1e-6

        # By node
        assert "build" in agg["by_node"]
        assert "review" in agg["by_node"]
        assert agg["by_node"]["build"]["count"] == 2
        assert agg["by_node"]["review"]["count"] == 1

        # By agent
        assert "codex" in agg["by_agent"]
        assert "claude" in agg["by_agent"]

    def test_filter_by_task_id(self, _isolate_workspace):
        from multi_agent.finops import aggregate_usage, record_task_usage

        record_task_usage(task_id="t1", node="build", input_tokens=100, output_tokens=50)
        record_task_usage(task_id="t2", node="build", input_tokens=200, output_tokens=100)

        agg = aggregate_usage(task_id="t1")
        assert agg["task_count"] == 1
        assert agg["total_tokens"] == 150


class TestFormatReport:
    def test_format_report_output(self, _isolate_workspace):
        from multi_agent.finops import format_report, record_task_usage

        record_task_usage(task_id="t1", node="build", input_tokens=1000, output_tokens=500, cost=0.01)
        report = format_report()
        assert "MyGO FinOps" in report
        assert "1,500" in report  # total tokens formatted
        assert "0.0100" in report


class TestCheckBudget:
    def test_no_budget_set(self, _isolate_workspace):
        from multi_agent.finops import check_budget

        result = check_budget()
        assert result["over_budget"] is False

    def test_under_budget(self, _isolate_workspace):
        from multi_agent.finops import check_budget, record_task_usage

        record_task_usage(task_id="t1", node="build", input_tokens=100, output_tokens=50, cost=0.001)
        result = check_budget(max_cost=1.0, max_tokens=1000)
        assert result["over_budget"] is False

    def test_over_cost_budget(self, _isolate_workspace):
        from multi_agent.finops import check_budget, record_task_usage

        record_task_usage(task_id="t1", node="build", input_tokens=100, output_tokens=50, cost=5.0)
        result = check_budget(max_cost=1.0)
        assert result["over_budget"] is True
        assert any("Cost" in w for w in result["warnings"])

    def test_over_token_budget(self, _isolate_workspace):
        from multi_agent.finops import check_budget, record_task_usage

        record_task_usage(task_id="t1", node="build", input_tokens=500000, output_tokens=600000)
        result = check_budget(max_tokens=100000)
        assert result["over_budget"] is True
        assert any("Tokens" in w for w in result["warnings"])


class TestCrossplatformTerminal:
    """Tests for driver.py cross-platform terminal detection."""

    def test_detect_terminal_emulator_returns_tuple_or_none(self):
        from multi_agent.driver import _detect_terminal_emulator

        result = _detect_terminal_emulator()
        # On macOS in CI, should find Terminal.app; on others may be None
        if result is not None:
            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], str)
            assert isinstance(result[1], list)

    @mock.patch("sys.platform", "darwin")
    @mock.patch("shutil.which", return_value="/usr/bin/osascript")
    def test_detect_macos(self, mock_which):
        from multi_agent.driver import _detect_terminal_emulator

        result = _detect_terminal_emulator()
        assert result is not None
        assert result[0] == "Terminal.app"

    @mock.patch("sys.platform", "linux")
    def test_detect_linux_gnome(self):
        from multi_agent.driver import _detect_terminal_emulator

        def which_side_effect(name):
            return "/usr/bin/gnome-terminal" if name == "gnome-terminal" else None

        with mock.patch("shutil.which", side_effect=which_side_effect):
            result = _detect_terminal_emulator()
            assert result is not None
            assert result[0] == "gnome-terminal"

    @mock.patch("sys.platform", "linux")
    @mock.patch("shutil.which", return_value=None)
    def test_detect_linux_none(self, mock_which):
        from multi_agent.driver import _detect_terminal_emulator

        result = _detect_terminal_emulator()
        assert result is None

    @mock.patch("sys.platform", "win32")
    def test_detect_windows_wt(self):
        from multi_agent.driver import _detect_terminal_emulator

        def which_side_effect(name):
            return "C:\\wt.exe" if name == "wt.exe" else None

        with mock.patch("shutil.which", side_effect=which_side_effect):
            result = _detect_terminal_emulator()
            assert result is not None
            assert result[0] == "Windows Terminal"


class TestDashboardAuth:
    """Tests for dashboard auth token flow in CLI."""

    def test_dashboard_command_has_token_option(self):
        from multi_agent.cli import dashboard

        params = {p.name for p in dashboard.params}
        assert "token" in params

    def test_auto_token_generates_string(self):
        import secrets
        token = secrets.token_urlsafe(24)
        assert len(token) >= 24
        assert isinstance(token, str)
