"""Tests for the LangGraph 4-node workflow."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from multi_agent.graph import (
    WorkflowState,
    build_graph,
    plan_node,
    decide_node,
    route_decision,
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
            "current_agent": "windsurf",
            "builder_agent": "windsurf",
            "conversation": [],
        }
        s.update(overrides)
        return s

    @patch("multi_agent.graph.write_dashboard")
    def test_approve(self, mock_dash):
        state = self._base_state(
            reviewer_output={"decision": "approve", "summary": "LGTM"}
        )
        result = decide_node(state)
        assert result["final_status"] == "approved"

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

    @patch("multi_agent.graph.write_dashboard")
    def test_reject_budget_exhausted(self, mock_dash):
        state = self._base_state(
            reviewer_output={"decision": "reject", "feedback": "still broken"},
            retry_count=2,
            retry_budget=2,
        )
        result = decide_node(state)
        assert result["error"] == "BUDGET_EXHAUSTED"
        assert result["final_status"] == "escalated"


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
