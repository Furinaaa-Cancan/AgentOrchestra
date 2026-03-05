from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from multi_agent.trace import (
    append_trace_event,
    read_trace,
    render_trace,
    trace_file,
)


@pytest.fixture
def trace_root(tmp_path, monkeypatch):
    (tmp_path / "skills").mkdir()
    (tmp_path / "agents").mkdir()
    monkeypatch.setenv("MA_ROOT", str(tmp_path))
    from multi_agent.config import root_dir

    root_dir.cache_clear()
    yield tmp_path
    root_dir.cache_clear()


def test_trace_append_and_render(trace_root):
    append_trace_event(
        task_id="task-trace-1",
        event_type="session_start",
        actor="codex",
        role="orchestrator",
        state="RUNNING",
        details={"x": 1},
    )
    append_trace_event(
        task_id="task-trace-1",
        event_type="handoff_submit",
        actor="windsurf",
        role="builder",
        state="RUNNING",
        details={"y": 2},
    )

    path = trace_file("task-trace-1")
    assert path.exists()

    events = read_trace("task-trace-1")
    assert len(events) == 2
    assert events[1]["parent_id"] == events[0]["event_id"]

    tree = render_trace("task-trace-1", "tree")
    assert "session_start" in tree
    assert "handoff_submit" in tree

    mermaid = render_trace("task-trace-1", "mermaid")
    assert "graph TD" in mermaid
    assert "-->" in mermaid


def test_trace_concurrent_append_keeps_linear_parent_chain(trace_root):
    task_id = "task-trace-concurrent"

    def _emit(i: int):
        append_trace_event(
            task_id=task_id,
            event_type="event",
            actor=f"agent-{i}",
            role="builder",
            state="RUNNING",
            details={"i": i},
        )

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(_emit, range(30)))

    events = read_trace(task_id)
    assert len(events) == 30
    assert len({e["event_id"] for e in events}) == 30
    for idx in range(1, len(events)):
        assert events[idx]["parent_id"] == events[idx - 1]["event_id"]


# ── Edge cases: corrupt/empty lines, empty trace, bad format ──


def test_read_trace_nonexistent(trace_root):
    """read_trace on missing file returns empty list (line 87)."""
    events = read_trace("task-nonexistent")
    assert events == []


def test_read_trace_with_blank_and_corrupt_lines(trace_root):
    """Blank lines and JSON decode errors are skipped (lines 93, 96-97)."""
    path = trace_file("task-corrupt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"event_id": "e1", "event_type": "start"}\n'
        "\n"
        "not json\n"
        '{"event_id": "e2", "event_type": "end"}\n',
        encoding="utf-8",
    )
    events = read_trace("task-corrupt")
    assert len(events) == 2
    assert events[0]["event_id"] == "e1"
    assert events[1]["event_id"] == "e2"


def test_render_trace_tree_empty(trace_root):
    """render_trace_tree with no events returns '(no events)' (line 115)."""
    from multi_agent.trace import render_trace_tree
    result = render_trace_tree("task-empty")
    assert "(no events)" in result


def test_render_trace_mermaid_empty(trace_root):
    """render_trace_mermaid with no events returns 'No events' (line 127)."""
    from multi_agent.trace import render_trace_mermaid
    result = render_trace_mermaid("task-empty")
    assert "No events" in result


def test_render_trace_mermaid_no_event_id(trace_root):
    """Events without event_id are skipped in mermaid render (line 133)."""
    from multi_agent.trace import render_trace_mermaid
    path = trace_file("task-noid")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"event_type": "orphan"}\n'
        '{"event_id": "e1", "event_type": "real"}\n',
        encoding="utf-8",
    )
    result = render_trace_mermaid("task-noid")
    assert "Ee1" in result
    assert "orphan" not in result or "Eorphan" not in result


def test_render_trace_unsupported_format(trace_root):
    """Unsupported format raises ValueError (line 148)."""
    with pytest.raises(ValueError, match="unsupported"):
        render_trace("task-trace-1", "xml")


def test_last_event_id_with_corrupt_lines(trace_root):
    """_read_last_event_id_from_handle skips blank and corrupt lines (lines 33, 36-37)."""
    from multi_agent.trace import _read_last_event_id_from_handle
    path = trace_file("task-last")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"event_id": "e1"}\n'
        "\n"
        "bad json\n"
        '{"event_id": "e2"}\n',
        encoding="utf-8",
    )
    with path.open("r") as f:
        result = _read_last_event_id_from_handle(f)
    assert result == "e2"
