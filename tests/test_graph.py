"""Tests for the LangGraph 4-node workflow."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from multi_agent.graph import (
    WorkflowState,
    build_graph,
    decide_node,
    route_decision,
    _route_after_build,
)


class TestRouteDecision:
    def test_approved(self):
        state = {"final_status": "approved", "reviewer_output": {"decision": "approve"}}
        assert route_decision(state) == "end"

    def test_error(self):
        state = {"error": "something broke"}
        assert route_decision(state) == "end"

    def test_retry(self):
        state = {"reviewer_output": {"decision": "reject"}}
        assert route_decision(state) == "retry"

    def test_no_output(self):
        state = {}
        assert route_decision(state) == "retry"


class TestDecideNode:
    def _base_state(self, **overrides) -> dict:
        s = {
            "task_id": "task-test-123",
            "skill_id": "code-implement",
            "done_criteria": ["implement something"],
            "retry_count": 0,
            "retry_budget": 2,
            "builder_id": "windsurf",
            "reviewer_id": "cursor",
            "conversation": [],
        }
        s.update(overrides)
        return s

    @patch("multi_agent.graph.archive_conversation")
    @patch("multi_agent.graph.write_dashboard")
    def test_approve(self, mock_dash, mock_archive):
        state = self._base_state(
            reviewer_output={"decision": "approve", "summary": "LGTM"}
        )
        result = decide_node(state)
        assert result["final_status"] == "approved"
        mock_archive.assert_called_once()

    @patch("multi_agent.graph.write_dashboard")
    def test_reject_with_budget(self, mock_dash):
        state = self._base_state(
            reviewer_output={"decision": "reject", "feedback": "fix tests"},
            retry_count=0,
            retry_budget=2,
        )
        result = decide_node(state)
        assert result["retry_count"] == 1
        assert "final_status" not in result

    @patch("multi_agent.graph.archive_conversation")
    @patch("multi_agent.graph.write_dashboard")
    def test_reject_budget_exhausted(self, mock_dash, mock_archive):
        state = self._base_state(
            reviewer_output={"decision": "reject", "feedback": "still broken"},
            retry_count=2,
            retry_budget=2,
        )
        result = decide_node(state)
        assert result["error"] == "BUDGET_EXHAUSTED"
        assert result["final_status"] == "escalated"
        mock_archive.assert_called_once()


class TestBuildNodeErrorDetection:
    """Test that build_node detects CLI driver error outputs."""

    @patch("multi_agent.graph.write_dashboard")
    @patch("multi_agent.graph._write_task_md")
    @patch("multi_agent.graph.interrupt")
    def test_cli_error_output_fails_build(self, mock_interrupt, mock_task_md, mock_dash):
        """status=error from CLI driver should NOT go to reviewer."""
        from multi_agent.graph import build_node
        mock_interrupt.return_value = {"status": "error", "summary": "claude CLI timed out after 600s"}
        state = {
            "builder_id": "claude",
            "reviewer_id": "cursor",
            "started_at": 0,
            "timeout_sec": 1800,
            "skill_id": "code-implement",
            "task_id": "task-test-err",
            "done_criteria": ["test"],
            "conversation": [],
        }
        result = build_node(state)
        assert result["final_status"] == "failed"
        assert "timed out" in result["error"]
        # Should NOT have builder_output (i.e., should not proceed to reviewer)
        assert "builder_output" not in result

    @patch("multi_agent.graph.write_dashboard")
    @patch("multi_agent.graph._write_task_md")
    @patch("multi_agent.graph.interrupt")
    def test_normal_output_passes_through(self, mock_interrupt, mock_task_md, mock_dash):
        """status=completed should proceed normally."""
        from multi_agent.graph import build_node
        mock_interrupt.return_value = {
            "status": "completed",
            "summary": "done",
            "changed_files": [],
            "check_results": {},
        }
        state = {
            "builder_id": "windsurf",
            "reviewer_id": "cursor",
            "started_at": 0,
            "timeout_sec": 1800,
            "skill_id": "code-implement",
            "task_id": "task-test-ok",
            "done_criteria": ["test"],
            "conversation": [],
            "input_payload": {"requirement": "test"},
        }
        result = build_node(state)
        assert "builder_output" in result
        assert "final_status" not in result


class TestReviewNodeErrorDetection:
    """Test that review_node detects CLI driver error outputs."""

    @patch("multi_agent.graph.interrupt")
    def test_reviewer_cli_error_auto_rejects(self, mock_interrupt):
        from multi_agent.graph import review_node
        mock_interrupt.return_value = {"status": "error", "summary": "codex CLI exited with code 1: OOM"}
        state = {
            "reviewer_id": "codex",
            "conversation": [],
        }
        result = review_node(state)
        assert result["reviewer_output"]["decision"] == "reject"
        assert "CLI failed" in result["reviewer_output"]["feedback"]
        assert "OOM" in result["reviewer_output"]["feedback"]


class TestRouteAfterBuild:
    def test_no_error_goes_to_review(self):
        state = {"builder_output": {"status": "completed"}}
        assert _route_after_build(state) == "review"

    def test_error_goes_to_end(self):
        state = {"error": "Builder output invalid"}
        assert _route_after_build(state) == "end"

    def test_failed_status_goes_to_end(self):
        state = {"final_status": "failed"}
        assert _route_after_build(state) == "end"

    def test_cancelled_status_goes_to_end(self):
        state = {"final_status": "cancelled"}
        assert _route_after_build(state) == "end"

    def test_empty_state_goes_to_review(self):
        assert _route_after_build({}) == "review"


class TestBuildGraph:
    def test_graph_structure(self):
        g = build_graph()
        compiled = g.compile()
        # Check that the graph has the expected nodes
        node_names = set(compiled.get_graph().nodes.keys())
        assert "plan" in node_names
        assert "build" in node_names
        assert "review" in node_names
        assert "decide" in node_names
