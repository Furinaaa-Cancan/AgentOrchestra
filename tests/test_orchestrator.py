"""Tests for orchestrator.py — shared graph coordination primitives."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from multi_agent.orchestrator import (
    TaskStartError,
    TaskStatus,
    _is_terminal,
    compile_graph,
    get_task_status,
    get_waiting_info,
    make_config,
    resume_task,
    start_task,
)

# ── Helpers ─────────────────────────────────────────────


def _make_snapshot(
    values: dict | None = None,
    has_next: bool = True,
    role: str = "builder",
    agent: str = "windsurf",
) -> SimpleNamespace:
    """Build a fake LangGraph StateSnapshot for testing."""
    interrupt = SimpleNamespace(value={"role": role, "agent": agent})
    task = SimpleNamespace(interrupts=[interrupt])
    return SimpleNamespace(
        values=values or {},
        next=["some_node"] if has_next else [],
        tasks=[task] if has_next else [],
    )


def _make_terminal_snapshot(
    final_status: str = "approved",
    error: str | None = None,
) -> SimpleNamespace:
    """Build a fake terminal StateSnapshot."""
    vals: dict = {"final_status": final_status}
    if error:
        vals["error"] = error
    return SimpleNamespace(values=vals, next=[], tasks=[])


# ── TaskStatus dataclass ────────────────────────────────


class TestTaskStatus:
    def test_frozen(self):
        ts = TaskStatus(state="RUNNING", is_terminal=False)
        with pytest.raises(AttributeError):
            ts.state = "DONE"  # type: ignore[misc]

    def test_defaults(self):
        ts = TaskStatus(state="RUNNING", is_terminal=False)
        assert ts.waiting_role is None
        assert ts.waiting_agent is None
        assert ts.final_status is None
        assert ts.error is None
        assert ts.values == {}

    def test_with_all_fields(self):
        ts = TaskStatus(
            state="DONE",
            is_terminal=True,
            waiting_role="builder",
            waiting_agent="windsurf",
            final_status="approved",
            error=None,
            values={"task_id": "t1"},
        )
        assert ts.state == "DONE"
        assert ts.is_terminal is True
        assert ts.values["task_id"] == "t1"


# ── _is_terminal ────────────────────────────────────────


class TestIsTerminal:
    @pytest.mark.parametrize("status", [
        "approved", "done", "failed", "escalated", "cancelled",
        "APPROVED", "Done", " Failed ", "ESCALATED",
    ])
    def test_terminal_statuses(self, status):
        assert _is_terminal(status) is True

    @pytest.mark.parametrize("status", [
        "", "running", "verifying", "assigned", "queued",
    ])
    def test_non_terminal_statuses(self, status):
        assert _is_terminal(status) is False

    def test_none(self):
        assert _is_terminal(None) is False


# ── make_config ─────────────────────────────────────────


class TestMakeConfig:
    def test_basic(self):
        cfg = make_config("task-123")
        assert cfg == {"configurable": {"thread_id": "task-123"}}

    def test_different_ids(self):
        assert make_config("a")["configurable"]["thread_id"] == "a"
        assert make_config("b")["configurable"]["thread_id"] == "b"


# ── compile_graph ───────────────────────────────────────


class TestCompileGraph:
    @patch("multi_agent.orchestrator.compile_graph.__module__", "multi_agent.orchestrator")
    def test_delegates_to_graph_module(self):
        mock_app = MagicMock()
        with patch("multi_agent.graph.compile_graph", return_value=mock_app) as mock_compile:
            result = compile_graph()
            mock_compile.assert_called_once()
            assert result is mock_app


# ── get_waiting_info ────────────────────────────────────


class TestGetWaitingInfo:
    def test_builder_interrupt(self):
        snap = _make_snapshot(role="builder", agent="windsurf")
        role, agent = get_waiting_info(snap)
        assert role == "builder"
        assert agent == "windsurf"

    def test_reviewer_interrupt(self):
        snap = _make_snapshot(role="reviewer", agent="cursor")
        role, agent = get_waiting_info(snap)
        assert role == "reviewer"
        assert agent == "cursor"

    def test_no_snapshot(self):
        assert get_waiting_info(None) == (None, None)

    def test_no_next(self):
        snap = SimpleNamespace(values={}, next=[], tasks=[])
        assert get_waiting_info(snap) == (None, None)

    def test_no_interrupts(self):
        task = SimpleNamespace(interrupts=[])
        snap = SimpleNamespace(values={}, next=["node"], tasks=[task])
        assert get_waiting_info(snap) == (None, None)

    def test_non_dict_interrupt_value(self):
        task = SimpleNamespace(interrupts=[SimpleNamespace(value="not-a-dict")])
        snap = SimpleNamespace(values={}, next=["node"], tasks=[task])
        assert get_waiting_info(snap) == (None, None)

    def test_non_string_role(self):
        task = SimpleNamespace(interrupts=[SimpleNamespace(value={"role": 123, "agent": "x"})])
        snap = SimpleNamespace(values={}, next=["node"], tasks=[task])
        assert get_waiting_info(snap) == (None, None)


# ── get_task_status ─────────────────────────────────────


class TestGetTaskStatus:
    def _app_returning(self, snapshot):
        app = MagicMock()
        app.get_state.return_value = snapshot
        return app

    def test_terminal_approved(self):
        app = self._app_returning(_make_terminal_snapshot("approved"))
        ts = get_task_status(app, "t1")
        assert ts.is_terminal is True
        assert ts.state == "DONE"
        assert ts.final_status == "approved"

    def test_terminal_failed(self):
        app = self._app_returning(_make_terminal_snapshot("failed", error="oops"))
        ts = get_task_status(app, "t1")
        assert ts.is_terminal is True
        assert ts.state == "FAILED"
        assert ts.error == "oops"

    def test_terminal_cancelled(self):
        app = self._app_returning(_make_terminal_snapshot("cancelled"))
        ts = get_task_status(app, "t1")
        assert ts.state == "CANCELLED"

    def test_terminal_escalated(self):
        app = self._app_returning(_make_terminal_snapshot("escalated"))
        ts = get_task_status(app, "t1")
        assert ts.state == "ESCALATED"

    def test_waiting_builder(self):
        snap = _make_snapshot(values={"task_id": "t1"}, role="builder", agent="windsurf")
        app = self._app_returning(snap)
        ts = get_task_status(app, "t1")
        assert ts.is_terminal is False
        assert ts.state == "RUNNING"
        assert ts.waiting_role == "builder"
        assert ts.waiting_agent == "windsurf"

    def test_waiting_reviewer(self):
        snap = _make_snapshot(values={"task_id": "t1"}, role="reviewer", agent="cursor")
        app = self._app_returning(snap)
        ts = get_task_status(app, "t1")
        assert ts.state == "VERIFYING"
        assert ts.waiting_role == "reviewer"

    def test_no_snapshot(self):
        app = self._app_returning(None)
        ts = get_task_status(app, "t1")
        # None snapshot → no next → terminal done
        assert ts.is_terminal is True
        assert ts.state == "DONE"

    def test_completed_without_final_status(self):
        snap = SimpleNamespace(values={}, next=[], tasks=[])
        app = self._app_returning(snap)
        ts = get_task_status(app, "t1")
        assert ts.is_terminal is True
        assert ts.final_status == "done"

    def test_uses_make_config(self):
        app = self._app_returning(_make_terminal_snapshot("done"))
        get_task_status(app, "task-xyz")
        app.get_state.assert_called_once_with({"configurable": {"thread_id": "task-xyz"}})

    def test_values_are_copied(self):
        """Ensure returned values dict is a copy, not a reference."""
        original = {"task_id": "t1", "final_status": "approved"}
        snap = SimpleNamespace(values=original, next=[], tasks=[])
        app = self._app_returning(snap)
        ts = get_task_status(app, "t1")
        ts.values["mutated"] = True
        assert "mutated" not in original


# ── start_task ──────────────────────────────────────────


class TestStartTask:
    def test_success_with_interrupt(self):
        from langgraph.errors import GraphInterrupt

        app = MagicMock()
        app.invoke.side_effect = GraphInterrupt()
        app.get_state.return_value = _make_snapshot(
            values={"task_id": "t1"}, role="builder", agent="windsurf",
        )

        ts = start_task(app, "t1", {"task_id": "t1"})
        assert ts.state == "RUNNING"
        assert ts.waiting_role == "builder"
        app.invoke.assert_called_once()

    def test_success_no_interrupt(self):
        app = MagicMock()
        app.invoke.return_value = None
        app.get_state.return_value = _make_terminal_snapshot("approved")

        ts = start_task(app, "t1", {"task_id": "t1"})
        assert ts.is_terminal is True

    def test_raises_task_start_error(self):
        app = MagicMock()
        app.invoke.side_effect = ValueError("kaboom")

        with pytest.raises(TaskStartError) as exc_info:
            start_task(app, "t1", {"task_id": "t1"})
        assert exc_info.value.task_id == "t1"
        assert isinstance(exc_info.value.cause, ValueError)
        assert "kaboom" in str(exc_info.value)

    def test_config_uses_task_id(self):
        from langgraph.errors import GraphInterrupt

        app = MagicMock()
        app.invoke.side_effect = GraphInterrupt()
        app.get_state.return_value = _make_snapshot()

        start_task(app, "my-task", {"task_id": "my-task"})
        call_args = app.invoke.call_args
        assert call_args[0][1] == {"configurable": {"thread_id": "my-task"}}


# ── resume_task ─────────────────────────────────────────


class TestResumeTask:
    def test_success_advances_to_reviewer(self):
        from langgraph.errors import GraphInterrupt

        app = MagicMock()
        app.invoke.side_effect = GraphInterrupt()
        app.get_state.return_value = _make_snapshot(role="reviewer", agent="cursor")

        ts = resume_task(app, "t1", {"summary": "done"})
        assert ts.state == "VERIFYING"
        assert ts.waiting_role == "reviewer"

    def test_success_terminal(self):
        app = MagicMock()
        app.invoke.return_value = None
        app.get_state.return_value = _make_terminal_snapshot("approved")

        ts = resume_task(app, "t1", {"summary": "done"})
        assert ts.is_terminal is True
        assert ts.final_status == "approved"

    def test_propagates_exception(self):
        app = MagicMock()
        app.invoke.side_effect = RuntimeError("graph crash")

        with pytest.raises(RuntimeError, match="graph crash"):
            resume_task(app, "t1", {"summary": "done"})

    def test_invokes_with_command(self):
        from langgraph.errors import GraphInterrupt
        from langgraph.types import Command

        app = MagicMock()
        app.invoke.side_effect = GraphInterrupt()
        app.get_state.return_value = _make_snapshot()

        data = {"summary": "test output"}
        resume_task(app, "t1", data)

        call_args = app.invoke.call_args[0]
        cmd = call_args[0]
        assert isinstance(cmd, Command)
        assert cmd.resume == data


# ── TaskStartError ──────────────────────────────────────


class TestTaskStartError:
    def test_attributes(self):
        cause = ValueError("root cause")
        err = TaskStartError("msg", task_id="t1", cause=cause)
        assert err.task_id == "t1"
        assert err.cause is cause
        assert str(err) == "msg"

    def test_is_runtime_error(self):
        err = TaskStartError("msg", task_id="t1")
        assert isinstance(err, RuntimeError)

    def test_cause_optional(self):
        err = TaskStartError("msg", task_id="t1")
        assert err.cause is None
