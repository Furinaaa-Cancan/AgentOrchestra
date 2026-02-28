"""Jinja2 prompt renderer — generates inbox prompts from templates."""

from __future__ import annotations

from pathlib import Path

from functools import lru_cache

from jinja2 import Environment, FileSystemLoader, select_autoescape

from multi_agent.config import root_dir
from multi_agent.schema import SkillContract, Task


def _template_dir() -> Path:
    """Resolve templates/ directory — inside the package (works after pip install)."""
    # Primary: templates bundled inside the package
    d = Path(__file__).parent / "templates"
    if d.is_dir():
        return d
    # Fallback: project root (dev mode / editable install)
    d = root_dir() / "templates"
    if d.is_dir():
        return d
    raise FileNotFoundError("Cannot find templates/ directory")


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_template_dir())),
        autoescape=select_autoescape([]),
        keep_trailing_newline=True,
    )


def render_builder_prompt(
    task: Task,
    contract: SkillContract,
    agent_id: str,
    retry_count: int = 0,
    retry_feedback: str = "",
    retry_budget: int = 2,
) -> str:
    """Render the builder prompt from builder.md.j2 template."""
    env = _env()
    tmpl = env.get_template("builder.md.j2")
    return tmpl.render(
        task=task,
        contract=contract,
        agent_id=agent_id,
        retry_count=retry_count,
        retry_feedback=retry_feedback,
        retry_budget=retry_budget,
    )


def render_reviewer_prompt(
    task: Task,
    contract: SkillContract,
    agent_id: str,
    builder_output: dict,
    builder_id: str,
) -> str:
    """Render the reviewer prompt from reviewer.md.j2 template."""
    env = _env()
    tmpl = env.get_template("reviewer.md.j2")
    return tmpl.render(
        task=task,
        contract=contract,
        agent_id=agent_id,
        builder_output=builder_output,
        builder_id=builder_id,
    )
