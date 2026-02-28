"""Tests for Pydantic schema models."""

import pytest

from multi_agent.schema import (
    AgentProfile,
    BackoffStrategy,
    BuilderOutput,
    CheckKind,
    Priority,
    ReviewDecision,
    ReviewerOutput,
    SkillContract,
    Task,
    TaskError,
    TaskState,
)


class TestTask:
    def test_valid_task(self):
        t = Task(
            task_id="task-abc-123",
            trace_id="a" * 16,
            skill_id="code-implement",
            done_criteria=["implement endpoint"],
            expected_checks=[CheckKind.LINT, CheckKind.UNIT_TEST],
        )
        assert t.state == TaskState.DRAFT
        assert t.priority == Priority.NORMAL
        assert t.retry_budget == 2

    def test_invalid_task_id(self):
        with pytest.raises(ValueError, match="task_id"):
            Task(task_id="INVALID", trace_id="a" * 16, skill_id="code-implement")

    def test_invalid_trace_id(self):
        with pytest.raises(ValueError, match="trace_id"):
            Task(task_id="task-abc", trace_id="ZZZ", skill_id="code-implement")

    def test_task_with_error(self):
        t = Task(
            task_id="task-err",
            trace_id="b" * 16,
            skill_id="code-implement",
            state=TaskState.FAILED,
            error=TaskError(code="TIMEOUT", message="ran too long"),
        )
        assert t.error.code == "TIMEOUT"


class TestSkillContract:
    def test_from_yaml(self):
        data = {
            "id": "code-implement",
            "version": "1.0.0",
            "description": "Apply scoped code changes",
            "quality_gates": ["lint", "unit_test"],
            "timeouts": {"run_sec": 1800, "verify_sec": 600},
            "retry": {"max_attempts": 2, "backoff": "linear"},
            "compatibility": {
                "min_orchestrator_version": "0.1.0",
                "supported_agents": ["codex", "windsurf"],
            },
        }
        c = SkillContract.from_yaml(data)
        assert c.id == "code-implement"
        assert c.supported_agents == ["codex", "windsurf"]
        assert c.timeouts.run_sec == 1800
        assert c.retry.backoff == BackoffStrategy.LINEAR

    def test_from_yaml_no_agents(self):
        data = {"id": "test-skill", "version": "1.0.0"}
        c = SkillContract.from_yaml(data)
        assert c.supported_agents == []


class TestAgentOutput:
    def test_builder_output(self):
        o = BuilderOutput(
            status="completed",
            summary="implemented endpoint",
            changed_files=["/src/main.py"],
            check_results={"lint": "pass", "unit_test": "pass"},
        )
        assert o.status == "completed"

    def test_reviewer_approve(self):
        o = ReviewerOutput(decision=ReviewDecision.APPROVE, summary="LGTM")
        assert o.decision == ReviewDecision.APPROVE

    def test_reviewer_reject(self):
        o = ReviewerOutput(
            decision=ReviewDecision.REJECT,
            issues=["missing validation"],
            feedback="Add email format check",
        )
        assert len(o.issues) == 1


class TestAgentProfile:
    def test_profile(self):
        p = AgentProfile(
            id="windsurf",
            capabilities=["planning", "implementation"],
            reliability=0.88,
            queue_health=0.91,
            cost=0.50,
        )
        assert p.id == "windsurf"
        assert "implementation" in p.capabilities

    def test_driver_defaults_to_file(self):
        p = AgentProfile(id="windsurf")
        assert p.driver == "file"
        assert p.command == ""

    def test_cli_driver_with_command(self):
        p = AgentProfile(
            id="claude",
            driver="cli",
            command="claude -p '{task_file}'",
        )
        assert p.driver == "cli"
        assert "{task_file}" in p.command
