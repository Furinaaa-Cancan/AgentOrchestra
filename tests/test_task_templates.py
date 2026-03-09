"""Tests for multi_agent.task_templates module."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture()
def templates_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary task-templates directory and patch root_dir."""
    tdir = tmp_path / "task-templates"
    tdir.mkdir()
    monkeypatch.setattr("multi_agent.task_templates.root_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "multi_agent.task_templates.load_project_config", lambda: {}
    )
    return tdir


def _write_template(tdir: Path, data: dict) -> Path:
    path = tdir / f"{data['id']}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


# ── list_templates ───────────────────────────────────────


class TestListTemplates:
    def test_empty(self, templates_dir: Path) -> None:
        from multi_agent.task_templates import list_templates

        assert list_templates() == []

    def test_discovers_templates(self, templates_dir: Path) -> None:
        from multi_agent.task_templates import list_templates

        _write_template(templates_dir, {
            "id": "alpha", "name": "Alpha", "requirement": "Do alpha",
        })
        _write_template(templates_dir, {
            "id": "beta", "name": "Beta", "requirement": "Do beta",
            "tags": ["test"],
        })

        result = list_templates()
        ids = [t.id for t in result]
        assert "alpha" in ids
        assert "beta" in ids

    def test_skips_invalid(self, templates_dir: Path) -> None:
        from multi_agent.task_templates import list_templates

        # Valid
        _write_template(templates_dir, {
            "id": "good", "name": "Good", "requirement": "Do good",
        })
        # Invalid (missing required fields)
        (templates_dir / "bad.yaml").write_text("just_a_string", encoding="utf-8")

        result = list_templates()
        assert len(result) == 1
        assert result[0].id == "good"

    def test_deduplicates_by_id(self, templates_dir: Path) -> None:
        from multi_agent.task_templates import list_templates

        _write_template(templates_dir, {
            "id": "dup", "name": "First", "requirement": "R1",
        })
        # Create a .yml variant with same id
        (templates_dir / "dup.yml").write_text(
            yaml.safe_dump({"id": "dup", "name": "Second", "requirement": "R2"}),
            encoding="utf-8",
        )

        result = list_templates()
        dup_templates = [t for t in result if t.id == "dup"]
        assert len(dup_templates) == 1


# ── load_template ────────────────────────────────────────


class TestLoadTemplate:
    def test_load_existing(self, templates_dir: Path) -> None:
        from multi_agent.task_templates import load_template

        _write_template(templates_dir, {
            "id": "mytempl", "name": "My Template",
            "requirement": "Do something",
            "skill": "test-and-review",
            "decompose": True,
            "tags": ["a", "b"],
            "variables": {"x": "1"},
        })

        tmpl = load_template("mytempl")
        assert tmpl.id == "mytempl"
        assert tmpl.name == "My Template"
        assert tmpl.skill == "test-and-review"
        assert tmpl.decompose is True
        assert tmpl.tags == ["a", "b"]
        assert tmpl.variables == {"x": "1"}

    def test_not_found(self, templates_dir: Path) -> None:
        from multi_agent.task_templates import TemplateNotFoundError, load_template

        with pytest.raises(TemplateNotFoundError, match="not found"):
            load_template("nonexistent")

    def test_invalid_id(self, templates_dir: Path) -> None:
        from multi_agent.task_templates import TemplateNotFoundError, load_template

        with pytest.raises(TemplateNotFoundError, match="Invalid template ID"):
            load_template("../escape")

    def test_validation_error(self, templates_dir: Path) -> None:
        from multi_agent.task_templates import TemplateValidationError, load_template

        # Missing 'name' and 'requirement'
        _write_template(templates_dir, {"id": "bad"})

        with pytest.raises(TemplateValidationError, match="Missing required"):
            load_template("bad")

    def test_defaults(self, templates_dir: Path) -> None:
        from multi_agent.task_templates import load_template

        _write_template(templates_dir, {
            "id": "minimal", "name": "Minimal", "requirement": "Do it",
        })

        tmpl = load_template("minimal")
        assert tmpl.skill == "code-implement"
        assert tmpl.builder == ""
        assert tmpl.reviewer == ""
        assert tmpl.retry_budget == 2
        assert tmpl.timeout == 1800
        assert tmpl.mode == "strict"
        assert tmpl.decompose is False
        assert tmpl.tags == []
        assert tmpl.variables == {}


# ── resolve_variables ────────────────────────────────────


class TestResolveVariables:
    def test_substitution(self, templates_dir: Path) -> None:
        from multi_agent.task_templates import TaskTemplate, resolve_variables

        tmpl = TaskTemplate({
            "id": "t", "name": "T", "requirement": "Build ${model} API",
            "variables": {"model": "User"},
        })
        resolved = resolve_variables(tmpl)
        assert resolved.requirement == "Build User API"

    def test_override(self, templates_dir: Path) -> None:
        from multi_agent.task_templates import TaskTemplate, resolve_variables

        tmpl = TaskTemplate({
            "id": "t", "name": "T", "requirement": "Fix ${module}",
            "variables": {"module": "default"},
        })
        resolved = resolve_variables(tmpl, {"module": "auth"})
        assert resolved.requirement == "Fix auth"

    def test_unresolved_left_intact(self, templates_dir: Path) -> None:
        from multi_agent.task_templates import TaskTemplate, resolve_variables

        tmpl = TaskTemplate({
            "id": "t", "name": "T", "requirement": "Use ${unknown}",
        })
        resolved = resolve_variables(tmpl)
        assert "${unknown}" in resolved.requirement

    def test_no_variables(self, templates_dir: Path) -> None:
        from multi_agent.task_templates import TaskTemplate, resolve_variables

        tmpl = TaskTemplate({
            "id": "t", "name": "T", "requirement": "Plain text",
        })
        resolved = resolve_variables(tmpl)
        assert resolved.requirement == "Plain text"


# ── parse_var_args ───────────────────────────────────────


class TestParseVarArgs:
    def test_basic(self) -> None:
        from multi_agent.task_templates import parse_var_args

        result = parse_var_args(["model=User", "table=users"])
        assert result == {"model": "User", "table": "users"}

    def test_value_with_equals(self) -> None:
        from multi_agent.task_templates import parse_var_args

        result = parse_var_args(["query=x=1&y=2"])
        assert result == {"query": "x=1&y=2"}

    def test_empty_value(self) -> None:
        from multi_agent.task_templates import parse_var_args

        result = parse_var_args(["key="])
        assert result == {"key": ""}

    def test_invalid_no_equals(self) -> None:
        from multi_agent.task_templates import parse_var_args

        with pytest.raises(ValueError, match="Expected key=value"):
            parse_var_args(["no_equals_sign"])

    def test_empty_key(self) -> None:
        from multi_agent.task_templates import parse_var_args

        with pytest.raises(ValueError, match="Empty key"):
            parse_var_args(["=value"])


# ── TaskTemplate.as_dict ─────────────────────────────────


class TestTaskTemplateAsDict:
    def test_roundtrip(self) -> None:
        from multi_agent.task_templates import TaskTemplate

        data = {
            "id": "t", "name": "T", "description": "D",
            "requirement": "R", "skill": "code-implement",
            "builder": "b", "reviewer": "r",
            "retry_budget": 3, "timeout": 600, "mode": "fast",
            "decompose": True, "tags": ["x"], "variables": {"k": "v"},
        }
        tmpl = TaskTemplate(data)
        d = tmpl.as_dict()
        for key in data:
            assert d[key] == data[key]


# ── Validation edge cases ────────────────────────────────


class TestValidation:
    def test_invalid_retry_budget(self, templates_dir: Path) -> None:
        from multi_agent.task_templates import _validate_template_data

        errors = _validate_template_data({
            "id": "t", "name": "T", "requirement": "R",
            "retry_budget": 99,
        })
        assert any("retry_budget" in e for e in errors)

    def test_invalid_timeout(self, templates_dir: Path) -> None:
        from multi_agent.task_templates import _validate_template_data

        errors = _validate_template_data({
            "id": "t", "name": "T", "requirement": "R",
            "timeout": -1,
        })
        assert any("timeout" in e for e in errors)

    def test_invalid_tags_type(self, templates_dir: Path) -> None:
        from multi_agent.task_templates import _validate_template_data

        errors = _validate_template_data({
            "id": "t", "name": "T", "requirement": "R",
            "tags": "not-a-list",
        })
        assert any("tags" in e for e in errors)

    def test_invalid_variables_type(self, templates_dir: Path) -> None:
        from multi_agent.task_templates import _validate_template_data

        errors = _validate_template_data({
            "id": "t", "name": "T", "requirement": "R",
            "variables": ["not", "a", "dict"],
        })
        assert any("variables" in e for e in errors)
