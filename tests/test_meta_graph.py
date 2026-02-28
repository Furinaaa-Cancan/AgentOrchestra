"""Tests for meta-graph orchestration module."""

from multi_agent.meta_graph import (
    generate_sub_task_id,
    build_sub_task_state,
    aggregate_results,
)
from multi_agent.schema import SubTask


class TestGenerateSubTaskId:
    def test_deterministic(self):
        id1 = generate_sub_task_id("parent-123", "auth-login")
        id2 = generate_sub_task_id("parent-123", "auth-login")
        assert id1 == id2

    def test_different_for_different_sub(self):
        id1 = generate_sub_task_id("parent-123", "auth-login")
        id2 = generate_sub_task_id("parent-123", "auth-register")
        assert id1 != id2

    def test_format(self):
        tid = generate_sub_task_id("parent-123", "step-1")
        assert tid.startswith("task-")
        assert len(tid) == 11  # "task-" + 6 hex chars


class TestBuildSubTaskState:
    def test_basic(self):
        st = SubTask(id="auth-login", description="Implement login")
        state = build_sub_task_state(st, "parent-abc")
        assert state["task_id"].startswith("task-")
        assert "Implement login" in state["requirement"]
        assert state["skill_id"] == "code-implement"
        assert state["retry_count"] == 0

    def test_with_prior_results(self):
        st = SubTask(id="auth-middleware", description="Implement middleware")
        prior = [
            {"sub_id": "auth-login", "summary": "Login done", "changed_files": ["/src/login.py"]},
        ]
        state = build_sub_task_state(st, "parent-abc", prior_results=prior)
        assert "auth-login" in state["requirement"]
        assert "Login done" in state["requirement"]
        assert "/src/login.py" in state["requirement"]

    def test_with_explicit_agents(self):
        st = SubTask(id="step-1", description="Do something")
        state = build_sub_task_state(
            st, "parent-abc", builder="windsurf", reviewer="cursor",
        )
        assert state["builder_explicit"] == "windsurf"
        assert state["reviewer_explicit"] == "cursor"

    def test_custom_timeout_and_budget(self):
        st = SubTask(id="step-1", description="Do something")
        state = build_sub_task_state(
            st, "parent-abc", timeout=900, retry_budget=3,
        )
        assert state["timeout_sec"] == 900
        assert state["retry_budget"] == 3


class TestAggregateResults:
    def test_all_approved(self):
        results = [
            {"sub_id": "a", "status": "approved", "summary": "Done A",
             "changed_files": ["/a.py"], "retry_count": 0},
            {"sub_id": "b", "status": "approved", "summary": "Done B",
             "changed_files": ["/b.py"], "retry_count": 1},
        ]
        agg = aggregate_results("parent-123", results)
        assert agg["final_status"] == "approved"
        assert agg["total_sub_tasks"] == 2
        assert agg["completed"] == 2
        assert agg["failed"] == []
        assert agg["total_retries"] == 1
        assert set(agg["all_changed_files"]) == {"/a.py", "/b.py"}

    def test_with_failure(self):
        results = [
            {"sub_id": "a", "status": "approved", "summary": "Done",
             "changed_files": [], "retry_count": 0},
            {"sub_id": "b", "status": "failed", "summary": "Crashed",
             "changed_files": [], "retry_count": 2},
        ]
        agg = aggregate_results("parent-123", results)
        assert agg["final_status"] == "failed"
        assert agg["completed"] == 1
        assert agg["failed"] == ["b"]

    def test_empty_results(self):
        agg = aggregate_results("parent-123", [])
        assert agg["total_sub_tasks"] == 0
        assert agg["final_status"] == "approved"

    def test_dedup_changed_files(self):
        results = [
            {"sub_id": "a", "status": "approved", "summary": "",
             "changed_files": ["/shared.py", "/a.py"], "retry_count": 0},
            {"sub_id": "b", "status": "approved", "summary": "",
             "changed_files": ["/shared.py", "/b.py"], "retry_count": 0},
        ]
        agg = aggregate_results("parent-123", results)
        assert len(agg["all_changed_files"]) == 3  # deduped
