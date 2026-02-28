"""Tests for Jinja2 prompt renderer."""

from pathlib import Path

import pytest

from multi_agent.contract import load_contract
from multi_agent.prompt import render_builder_prompt, render_reviewer_prompt, _template_dir
from multi_agent.schema import Task


SKILLS_DIR = Path(__file__).parent.parent / "skills"


def _make_task(**overrides) -> Task:
    defaults = {
        "task_id": "task-test-abc",
        "trace_id": "a" * 16,
        "skill_id": "code-implement",
        "done_criteria": ["implement X", "add tests"],
        "input_payload": {"requirement": "Add input validation"},
    }
    defaults.update(overrides)
    return Task(**defaults)


class TestTemplateDir:
    def test_finds_templates(self):
        d = _template_dir()
        assert d.is_dir()
        assert (d / "builder.md.j2").exists()
        assert (d / "reviewer.md.j2").exists()


class TestRenderBuilderPrompt:
    def test_basic_render(self):
        task = _make_task()
        contract = load_contract("code-implement", base=SKILLS_DIR)
        result = render_builder_prompt(task, contract, agent_id="windsurf")
        # Should contain key sections
        assert "Builder" in result
        assert "windsurf" in result
        assert "implement X" in result
        assert "add tests" in result
        assert "code-implement" in result
        # Should contain output JSON template
        assert '"status"' in result
        assert '"summary"' in result

    def test_includes_quality_gates(self):
        task = _make_task()
        contract = load_contract("code-implement", base=SKILLS_DIR)
        result = render_builder_prompt(task, contract, agent_id="windsurf")
        assert "lint" in result
        assert "unit_test" in result

    def test_retry_section_absent_on_first_try(self):
        task = _make_task()
        contract = load_contract("code-implement", base=SKILLS_DIR)
        result = render_builder_prompt(task, contract, agent_id="windsurf", retry_count=0)
        assert "重试" not in result

    def test_retry_section_present_on_retry(self):
        task = _make_task()
        contract = load_contract("code-implement", base=SKILLS_DIR)
        result = render_builder_prompt(
            task, contract, agent_id="windsurf",
            retry_count=1, retry_feedback="fix the tests", retry_budget=2,
        )
        assert "重试" in result
        assert "fix the tests" in result
        assert "1" in result  # retry count

    def test_input_payload_rendered(self):
        task = _make_task()
        contract = load_contract("code-implement", base=SKILLS_DIR)
        result = render_builder_prompt(task, contract, agent_id="windsurf")
        assert "requirement" in result
        assert "Add input validation" in result


class TestRenderReviewerPrompt:
    def test_basic_render(self):
        task = _make_task()
        contract = load_contract("code-implement", base=SKILLS_DIR)
        builder_output = {
            "status": "completed",
            "summary": "Added validation logic",
            "changed_files": ["/src/main.py"],
            "check_results": {"lint": "pass", "unit_test": "pass"},
            "risks": [],
            "handoff_notes": "check edge cases",
        }
        result = render_reviewer_prompt(
            task, contract, agent_id="cursor",
            builder_output=builder_output, builder_id="windsurf",
        )
        assert "Reviewer" in result
        assert "cursor" in result
        assert "windsurf" in result
        assert "Added validation logic" in result
        assert "/src/main.py" in result
        assert "check edge cases" in result

    def test_includes_decision_template(self):
        task = _make_task()
        contract = load_contract("code-implement", base=SKILLS_DIR)
        builder_output = {"status": "completed", "summary": "done", "check_results": {}}
        result = render_reviewer_prompt(
            task, contract, agent_id="cursor",
            builder_output=builder_output, builder_id="windsurf",
        )
        assert '"decision"' in result
        assert "approve" in result
        assert "reject" in result

    def test_gate_warnings_displayed(self):
        task = _make_task()
        contract = load_contract("code-implement", base=SKILLS_DIR)
        builder_output = {
            "status": "completed",
            "summary": "done",
            "check_results": {"lint": "pass"},
            "gate_warnings": ["quality gate 'unit_test' not reported"],
        }
        result = render_reviewer_prompt(
            task, contract, agent_id="cursor",
            builder_output=builder_output, builder_id="windsurf",
        )
        assert "unit_test" in result
