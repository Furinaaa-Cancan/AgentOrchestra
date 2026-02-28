"""Tests for agent driver — CLI spawn and file fallback."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from multi_agent import driver


class TestGetAgentDriver:
    def test_cli_agent(self):
        from multi_agent.schema import AgentProfile
        agents = [
            AgentProfile(id="claude", driver="cli", command="claude -p '{task_file}'"),
            AgentProfile(id="windsurf", driver="file"),
        ]
        with patch("multi_agent.router.load_agents", return_value=agents):
            drv = driver.get_agent_driver("claude")
            assert drv["driver"] == "cli"
            assert "claude" in drv["command"]

    def test_file_agent(self):
        from multi_agent.schema import AgentProfile
        agents = [AgentProfile(id="windsurf", driver="file")]
        with patch("multi_agent.router.load_agents", return_value=agents):
            drv = driver.get_agent_driver("windsurf")
            assert drv["driver"] == "file"
            assert drv["command"] == ""

    def test_unknown_agent_defaults_to_file(self):
        with patch("multi_agent.router.load_agents", return_value=[]):
            drv = driver.get_agent_driver("unknown")
            assert drv["driver"] == "file"

    def test_missing_driver_field_defaults_to_file(self):
        from multi_agent.schema import AgentProfile
        agents = [AgentProfile(id="old_agent")]
        with patch("multi_agent.router.load_agents", return_value=agents):
            drv = driver.get_agent_driver("old_agent")
            assert drv["driver"] == "file"


class TestTryExtractJson:
    def test_extracts_from_code_block(self, tmp_path):
        text = 'Here is the result:\n```json\n{"status": "completed", "summary": "done"}\n```\nDone.'
        outbox = tmp_path / "builder.json"
        driver._try_extract_json(text, outbox)
        assert outbox.exists()
        data = json.loads(outbox.read_text())
        assert data["status"] == "completed"

    def test_extracts_raw_json(self, tmp_path):
        text = '{"status": "completed", "summary": "raw"}'
        outbox = tmp_path / "builder.json"
        driver._try_extract_json(text, outbox)
        assert outbox.exists()
        data = json.loads(outbox.read_text())
        assert data["summary"] == "raw"

    def test_ignores_non_json(self, tmp_path):
        text = "This is not JSON at all"
        outbox = tmp_path / "builder.json"
        driver._try_extract_json(text, outbox)
        assert not outbox.exists()

    def test_ignores_non_dict_json(self, tmp_path):
        text = '["not", "a", "dict"]'
        outbox = tmp_path / "builder.json"
        driver._try_extract_json(text, outbox)
        assert not outbox.exists()


class TestWriteError:
    def test_writes_error_json(self, tmp_path):
        outbox = str(tmp_path / "outbox" / "builder.json")
        driver._write_error(outbox, "timeout")
        data = json.loads(Path(outbox).read_text())
        assert data["status"] == "error"
        assert "timeout" in data["summary"]


class TestSpawnCliAgent:
    def test_spawns_echo_command(self, tmp_path):
        """Test that spawn_cli_agent runs a command and writes outbox."""
        outbox_dir = tmp_path / "outbox"
        outbox_dir.mkdir()
        outbox_file = outbox_dir / "builder.json"

        # Command that writes JSON directly to {outbox_file}
        cmd = 'echo \'{{"status": "completed", "summary": "test"}}\' > {outbox_file}'

        with patch("multi_agent.driver.workspace_dir", return_value=tmp_path), \
             patch("multi_agent.driver.outbox_dir", return_value=outbox_dir):
            t = driver.spawn_cli_agent("test", "builder", cmd, str(tmp_path))
            t.join(timeout=10)

        assert outbox_file.exists()
        data = json.loads(outbox_file.read_text())
        assert data["status"] == "completed"

    def test_timeout_writes_error(self, tmp_path):
        """Test that timeout produces an error in outbox."""
        outbox_dir = tmp_path / "outbox"
        outbox_dir.mkdir()

        import subprocess as real_subprocess
        cmd = "sleep 999"

        def fake_run(*args, **kwargs):
            raise real_subprocess.TimeoutExpired(cmd, 600)

        with patch("multi_agent.driver.workspace_dir", return_value=tmp_path), \
             patch("multi_agent.driver.outbox_dir", return_value=outbox_dir), \
             patch("multi_agent.driver.subprocess.run", side_effect=fake_run):
            t = driver.spawn_cli_agent("test", "builder", cmd, str(tmp_path))
            t.join(timeout=10)

        outbox_file = outbox_dir / "builder.json"
        assert outbox_file.exists()
        data = json.loads(outbox_file.read_text())
        assert data["status"] == "error"
        assert "timed out" in data["summary"]
