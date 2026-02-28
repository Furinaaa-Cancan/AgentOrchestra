"""Tests for task decomposition module."""

import json
import pytest
from pathlib import Path

from multi_agent.decompose import (
    parse_decompose_json,
    topo_sort,
    write_decompose_prompt,
    read_decompose_result,
)
from multi_agent.schema import SubTask, DecomposeResult


class TestParseDecomposeJson:
    def test_parse_raw_json(self):
        raw = json.dumps({
            "sub_tasks": [
                {"id": "auth-login", "description": "Implement login", "done_criteria": ["login works"]},
                {"id": "auth-register", "description": "Implement register"},
            ],
            "reasoning": "Split by feature",
        })
        result = parse_decompose_json(raw)
        assert result is not None
        assert len(result.sub_tasks) == 2
        assert result.sub_tasks[0].id == "auth-login"
        assert result.reasoning == "Split by feature"

    def test_parse_markdown_fenced(self):
        raw = """Here is the decomposition:

```json
{
  "sub_tasks": [
    {"id": "step-1", "description": "First step"}
  ],
  "reasoning": "Simple"
}
```

Done!"""
        result = parse_decompose_json(raw)
        assert result is not None
        assert len(result.sub_tasks) == 1
        assert result.sub_tasks[0].id == "step-1"

    def test_parse_invalid_json(self):
        assert parse_decompose_json("not json at all") is None

    def test_parse_missing_sub_tasks(self):
        raw = json.dumps({"reasoning": "no sub_tasks key"})
        assert parse_decompose_json(raw) is None

    def test_parse_empty_string(self):
        assert parse_decompose_json("") is None


class TestTopoSort:
    def test_no_deps(self):
        tasks = [
            SubTask(id="a", description="A"),
            SubTask(id="b", description="B"),
            SubTask(id="c", description="C"),
        ]
        sorted_tasks = topo_sort(tasks)
        ids = [t.id for t in sorted_tasks]
        assert set(ids) == {"a", "b", "c"}

    def test_linear_deps(self):
        tasks = [
            SubTask(id="c", description="C", deps=["b"]),
            SubTask(id="b", description="B", deps=["a"]),
            SubTask(id="a", description="A"),
        ]
        sorted_tasks = topo_sort(tasks)
        ids = [t.id for t in sorted_tasks]
        assert ids == ["a", "b", "c"]

    def test_diamond_deps(self):
        tasks = [
            SubTask(id="d", description="D", deps=["b", "c"]),
            SubTask(id="b", description="B", deps=["a"]),
            SubTask(id="c", description="C", deps=["a"]),
            SubTask(id="a", description="A"),
        ]
        sorted_tasks = topo_sort(tasks)
        ids = [t.id for t in sorted_tasks]
        assert ids[0] == "a"  # a must be first
        assert ids[-1] == "d"  # d must be last
        assert ids.index("b") < ids.index("d")
        assert ids.index("c") < ids.index("d")

    def test_circular_dep_raises(self):
        tasks = [
            SubTask(id="a", description="A", deps=["b"]),
            SubTask(id="b", description="B", deps=["a"]),
        ]
        with pytest.raises(ValueError, match="Circular"):
            topo_sort(tasks)

    def test_unknown_dep_raises(self):
        tasks = [
            SubTask(id="a", description="A", deps=["nonexistent"]),
        ]
        with pytest.raises(ValueError, match="Unknown dependency"):
            topo_sort(tasks)

    def test_single_task(self):
        tasks = [SubTask(id="only", description="Only task")]
        sorted_tasks = topo_sort(tasks)
        assert len(sorted_tasks) == 1
        assert sorted_tasks[0].id == "only"


class TestWriteAndRead:
    def test_write_decompose_prompt(self, tmp_path, monkeypatch):
        monkeypatch.setattr("multi_agent.decompose.workspace_dir", lambda: tmp_path)
        monkeypatch.setattr("multi_agent.decompose.outbox_dir", lambda: tmp_path / "outbox")
        monkeypatch.setattr("multi_agent.decompose.inbox_dir", lambda: tmp_path / "inbox")

        p = write_decompose_prompt("Build auth module")
        assert p.exists()
        content = p.read_text()
        assert "Build auth module" in content
        assert "sub_tasks" in content

    def test_read_decompose_result(self, tmp_path, monkeypatch):
        outbox = tmp_path / "outbox"
        outbox.mkdir()
        monkeypatch.setattr("multi_agent.decompose.outbox_dir", lambda: outbox)

        data = {
            "sub_tasks": [
                {"id": "step-1", "description": "First"},
                {"id": "step-2", "description": "Second", "deps": ["step-1"]},
            ],
            "reasoning": "test",
        }
        (outbox / "decompose.json").write_text(json.dumps(data))

        result = read_decompose_result()
        assert result is not None
        assert len(result.sub_tasks) == 2

    def test_read_markdown_fenced_json(self, tmp_path, monkeypatch):
        """Agent may wrap JSON in ```json blocks — fallback should handle it."""
        outbox = tmp_path / "outbox"
        outbox.mkdir()
        monkeypatch.setattr("multi_agent.decompose.outbox_dir", lambda: outbox)

        fenced = '''Here is my decomposition:

```json
{
  "sub_tasks": [{"id": "step-1", "description": "Do it"}],
  "reasoning": "simple"
}
```
'''
        (outbox / "decompose.json").write_text(fenced)
        result = read_decompose_result()
        assert result is not None
        assert result.sub_tasks[0].id == "step-1"

    def test_read_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("multi_agent.decompose.outbox_dir", lambda: tmp_path / "nope")
        assert read_decompose_result() is None
