"""Skill contract loader — reads YAML contracts from skills/ directory."""

from __future__ import annotations

from pathlib import Path

from multi_agent.config import skills_dir, load_yaml
from multi_agent.schema import SkillContract


def load_contract(skill_id: str, base: Path | None = None) -> SkillContract:
    """Load a skill contract by id from ``skills/{skill_id}/contract.yaml``."""
    base = base or skills_dir()
    path = base / skill_id / "contract.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Skill contract not found: {path}")
    data = load_yaml(path)
    return SkillContract.from_yaml(data)


def list_skills(base: Path | None = None) -> list[str]:
    """Return available skill ids."""
    base = base or skills_dir()
    return sorted(
        d.name
        for d in base.iterdir()
        if d.is_dir() and (d / "contract.yaml").exists()
    )


def validate_preconditions(contract: SkillContract, state: str) -> list[str]:
    """Light-weight precondition check. Returns list of violation messages."""
    errors: list[str] = []
    for cond in contract.preconditions:
        lower = cond.lower()
        if "task state is running" in lower and state != "RUNNING":
            errors.append(f"precondition requires RUNNING, current state is {state}")
    return errors
