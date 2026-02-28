"""Tests for the OutboxPoller — including partial write race condition."""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from multi_agent.watcher import OutboxPoller


@pytest.fixture
def tmp_outbox(tmp_path, monkeypatch):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    monkeypatch.setattr("multi_agent.watcher.outbox_dir", lambda: outbox)
    return outbox


class TestCheckOnce:
    def test_detects_new_file(self, tmp_outbox):
        poller = OutboxPoller()
        # No files yet
        assert poller.check_once() == []

        # Write valid builder output
        (tmp_outbox / "builder.json").write_text(
            json.dumps({"status": "completed", "summary": "done"}),
            encoding="utf-8",
        )
        results = poller.check_once()
        assert len(results) == 1
        assert results[0][0] == "builder"
        assert results[0][1]["status"] == "completed"

    def test_ignores_already_seen(self, tmp_outbox):
        poller = OutboxPoller()
        (tmp_outbox / "builder.json").write_text(
            json.dumps({"status": "completed", "summary": "done"}),
            encoding="utf-8",
        )
        # First check — detected
        assert len(poller.check_once()) == 1
        # Second check — same mtime, not re-detected
        assert len(poller.check_once()) == 0

    def test_detects_updated_file(self, tmp_outbox):
        poller = OutboxPoller()
        path = tmp_outbox / "builder.json"
        path.write_text(json.dumps({"status": "v1", "summary": "first"}))
        poller.check_once()

        # Update with new mtime
        time.sleep(0.05)
        path.write_text(json.dumps({"status": "v2", "summary": "second"}))
        results = poller.check_once()
        assert len(results) == 1
        assert results[0][1]["status"] == "v2"

    def test_partial_write_retries(self, tmp_outbox):
        """CRITICAL: partial JSON must NOT mark file as seen."""
        poller = OutboxPoller()
        path = tmp_outbox / "builder.json"

        # Write partial/corrupt JSON
        path.write_text('{"status": "complet', encoding="utf-8")
        results = poller.check_once()
        assert results == []  # JSONDecodeError — not detected

        # _known should NOT have been updated
        assert "builder" not in poller._known

        # Now write complete JSON (same or newer mtime)
        time.sleep(0.05)
        path.write_text(
            json.dumps({"status": "completed", "summary": "done"}),
            encoding="utf-8",
        )
        results = poller.check_once()
        assert len(results) == 1  # NOW detected
        assert results[0][1]["status"] == "completed"

    def test_ignores_non_dict_json(self, tmp_outbox):
        poller = OutboxPoller()
        (tmp_outbox / "builder.json").write_text("[1, 2, 3]")
        results = poller.check_once()
        assert results == []
        # Should NOT mark as seen (non-dict)
        assert "builder" not in poller._known

    def test_multiple_roles(self, tmp_outbox):
        poller = OutboxPoller()
        (tmp_outbox / "builder.json").write_text(
            json.dumps({"status": "completed", "summary": "b"})
        )
        (tmp_outbox / "reviewer.json").write_text(
            json.dumps({"decision": "approve", "summary": "r"})
        )
        results = poller.check_once()
        roles = {r[0] for r in results}
        assert roles == {"builder", "reviewer"}

    def test_missing_outbox_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "multi_agent.watcher.outbox_dir", lambda: tmp_path / "nonexistent"
        )
        poller = OutboxPoller()
        assert poller.check_once() == []
