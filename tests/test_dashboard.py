"""Tests for the dashboard generator."""

import pytest

from multi_agent.dashboard import generate_dashboard, write_dashboard


class TestGenerateDashboard:
    def test_basic_content(self):
        content = generate_dashboard(
            task_id="task-abc123",
            done_criteria=["implement X", "add tests"],
            current_agent="windsurf",
            current_role="builder",
            conversation=[],
        )
        assert "task-abc123" in content
        assert "implement X" in content
        assert "add tests" in content

    def test_references_task_md_not_inbox(self):
        content = generate_dashboard(
            task_id="task-abc",
            done_criteria=[],
            current_agent="windsurf",
            current_role="builder",
            conversation=[],
        )
        assert "TASK.md" in content
        assert "inbox" not in content.lower()

    def test_error_display(self):
        content = generate_dashboard(
            task_id="task-abc",
            done_criteria=[],
            current_agent="windsurf",
            current_role="builder",
            conversation=[],
            error="something broke",
        )
        assert "something broke" in content
        assert "❌" in content

    def test_status_msg(self):
        content = generate_dashboard(
            task_id="task-abc",
            done_criteria=[],
            current_agent="cursor",
            current_role="reviewer",
            conversation=[],
            status_msg="🟡 等待审查",
        )
        assert "等待审查" in content

    def test_conversation_history(self):
        content = generate_dashboard(
            task_id="task-abc",
            done_criteria=[],
            current_agent="windsurf",
            current_role="builder",
            conversation=[
                {"role": "orchestrator", "action": "assigned"},
                {"role": "builder", "output": "done"},
            ],
        )
        assert "orchestrator" in content
        assert "assigned" in content

    def test_fallback_role_display(self):
        """When no status_msg or error, should show role-based display."""
        content = generate_dashboard(
            task_id="task-abc",
            done_criteria=[],
            current_agent="windsurf",
            current_role="builder",
            conversation=[],
        )
        assert "windsurf" in content
        assert "builder" in content


class TestWriteDashboard:
    def test_writes_to_disk(self, tmp_path):
        p = tmp_path / "dashboard.md"
        result = write_dashboard(
            task_id="task-abc",
            done_criteria=["test"],
            current_agent="windsurf",
            current_role="builder",
            conversation=[],
            path=p,
        )
        assert result == p
        assert p.exists()
        assert "task-abc" in p.read_text()
