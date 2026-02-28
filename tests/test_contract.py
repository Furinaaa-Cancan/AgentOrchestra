"""Tests for skill contract loader."""

import pytest
from pathlib import Path

from multi_agent.contract import load_contract, list_skills, validate_preconditions


SKILLS_DIR = Path(__file__).parent.parent / "skills"


class TestLoadContract:
    def test_load_code_implement(self):
        c = load_contract("code-implement", base=SKILLS_DIR)
        assert c.id == "code-implement"
        assert c.version == "1.0.0"
        assert "lint" in c.quality_gates
        assert c.timeouts.run_sec == 1800
        assert c.retry.max_attempts == 2

    def test_load_test_and_review(self):
        c = load_contract("test-and-review", base=SKILLS_DIR)
        assert c.id == "test-and-review"

    def test_load_task_decompose(self):
        c = load_contract("task-decompose", base=SKILLS_DIR)
        assert c.id == "task-decompose"

    def test_load_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            load_contract("no-such-skill", base=SKILLS_DIR)


class TestListSkills:
    def test_list(self):
        skills = list_skills(base=SKILLS_DIR)
        assert "code-implement" in skills
        assert "test-and-review" in skills
        assert "task-decompose" in skills


class TestPreconditions:
    def test_running_ok(self):
        c = load_contract("code-implement", base=SKILLS_DIR)
        errors = validate_preconditions(c, "RUNNING")
        assert errors == []

    def test_not_running(self):
        c = load_contract("code-implement", base=SKILLS_DIR)
        errors = validate_preconditions(c, "ASSIGNED")
        assert len(errors) > 0
