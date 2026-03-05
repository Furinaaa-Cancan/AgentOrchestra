from __future__ import annotations

from pathlib import Path

import pytest

from multi_agent.memory import (
    add_pending_candidates,
    ensure_memory_file,
    memory_file,
    pending_file,
    promote_pending_candidates,
)


@pytest.fixture
def memory_root(tmp_path, monkeypatch):
    (tmp_path / "skills").mkdir()
    (tmp_path / "agents").mkdir()
    monkeypatch.setenv("MA_ROOT", str(tmp_path))
    from multi_agent.config import root_dir

    root_dir.cache_clear()
    yield tmp_path
    root_dir.cache_clear()


def test_memory_pending_and_promote(memory_root: Path):
    ensure_memory_file()
    assert memory_file().exists()

    add_result = add_pending_candidates(
        "task-memory-1",
        ["Use absolute paths in outbox artifacts", {"content": "Reviewer must provide evidence", "source": "policy"}],
        actor="antigravity",
    )
    assert add_result["added"] == 2
    assert pending_file("task-memory-1").exists()

    promote_result = promote_pending_candidates("task-memory-1", actor="orchestrator")
    assert promote_result["applied"] == 2
    text = memory_file().read_text(encoding="utf-8")
    assert "Use absolute paths in outbox artifacts" in text
    assert "Reviewer must provide evidence" in text


def test_memory_deduplicates_items(memory_root: Path):
    ensure_memory_file()
    add_pending_candidates("task-memory-2", ["A", "A", "  A  "], actor="builder")
    promote_pending_candidates("task-memory-2", actor="orchestrator")
    before = memory_file().read_text(encoding="utf-8")

    add_pending_candidates("task-memory-2", ["A"], actor="builder")
    result = promote_pending_candidates("task-memory-2", actor="orchestrator")
    assert result["applied"] == 0
    after = memory_file().read_text(encoding="utf-8")
    assert before == after


# ── Edge cases for _normalize_item (lines 42, 45) ───────


def test_normalize_item_dict_empty_content(memory_root: Path):
    """Dict item with empty content returns None → skipped."""
    ensure_memory_file()
    result = add_pending_candidates("task-norm-1", [{"content": "", "source": "x"}], actor="builder")
    assert result["added"] == 0


def test_normalize_item_non_string_non_dict(memory_root: Path):
    """Non-string/non-dict items (int, None, list) are skipped."""
    ensure_memory_file()
    result = add_pending_candidates("task-norm-2", [42, None, [1, 2]], actor="builder")
    assert result["added"] == 0


# ── Corrupt pending file (lines 53-56, 60, 64) ──────────


def test_add_pending_corrupt_json(memory_root: Path):
    """Pending file with invalid JSON → reset to empty."""
    ensure_memory_file()
    p = pending_file("task-corrupt-1")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{bad json", encoding="utf-8")
    result = add_pending_candidates("task-corrupt-1", ["good item"], actor="builder")
    assert result["added"] == 1


def test_add_pending_non_dict_payload(memory_root: Path):
    """Pending file containing a JSON list → treat as empty dict."""
    ensure_memory_file()
    p = pending_file("task-corrupt-2")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("[1,2,3]", encoding="utf-8")
    result = add_pending_candidates("task-corrupt-2", ["new"], actor="builder")
    assert result["added"] == 1


def test_add_pending_items_not_list(memory_root: Path):
    """Pending file with items as string → reset to empty list."""
    import json
    ensure_memory_file()
    p = pending_file("task-corrupt-3")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"items": "not-a-list"}), encoding="utf-8")
    result = add_pending_candidates("task-corrupt-3", ["x"], actor="builder")
    assert result["added"] == 1


# ── promote edge cases (lines 109-110, 113, 121) ────────


def test_promote_corrupt_json(memory_root: Path):
    """Promote with corrupt pending JSON → reason message."""
    ensure_memory_file()
    p = pending_file("task-promote-bad")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("not json!", encoding="utf-8")
    result = promote_pending_candidates("task-promote-bad", actor="orchestrator")
    assert result["applied"] == 0
    assert "invalid JSON" in result["reason"]


def test_promote_items_not_list(memory_root: Path):
    """Promote with items as non-list → reason message."""
    import json
    ensure_memory_file()
    p = pending_file("task-promote-bad2")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"items": "string"}), encoding="utf-8")
    result = promote_pending_candidates("task-promote-bad2", actor="orchestrator")
    assert result["applied"] == 0
    assert "not a list" in result["reason"]


def test_promote_non_string_items_skipped(memory_root: Path):
    """Non-string items in pending list are skipped during promote."""
    import json
    ensure_memory_file()
    p = pending_file("task-promote-mixed")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"items": [42, "valid item", None]}), encoding="utf-8")
    result = promote_pending_candidates("task-promote-mixed", actor="orchestrator")
    assert result["applied"] == 1
