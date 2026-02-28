"""Agent router — IDE-agnostic role assignment.

Supports two strategies:
  - manual: user specifies which IDE fills each role (default, best UX)
  - auto:   system picks based on capabilities (legacy)

Works with ANY IDE: Windsurf, Cursor, Codex, Kiro, Antigravity, Copilot, Aider, ...
"""

from __future__ import annotations

import json
from pathlib import Path

from multi_agent.config import agents_profile_path, load_yaml, root_dir
from multi_agent.schema import AgentProfile, SkillContract


# ── Registry Loading ──────────────────────────────────────

def _agents_yaml_path() -> Path:
    return root_dir() / "agents" / "agents.yaml"


def load_registry(path: Path | None = None) -> dict:
    """Load agents.yaml v2 registry. Falls back to profiles.json."""
    yaml_path = path or _agents_yaml_path()
    if yaml_path.exists():
        return load_yaml(yaml_path)
    # Fallback: legacy profiles.json
    json_path = agents_profile_path()
    if json_path.exists():
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {"version": 1, "agents": data["agents"], "role_strategy": "auto"}
    return {"version": 2, "agents": [], "role_strategy": "manual", "defaults": {}}


def load_agents(path: Path | None = None) -> list[AgentProfile]:
    """Load agent profiles from registry."""
    reg = load_registry(path)
    agents_data = reg.get("agents", [])
    result = []
    for a in agents_data:
        # agents.yaml v2 uses simpler format (no reliability/cost fields required)
        profile = AgentProfile(
            id=a["id"],
            capabilities=a.get("capabilities", []),
            reliability=a.get("reliability", 0.9),
            queue_health=a.get("queue_health", 0.9),
            cost=a.get("cost", 0.5),
        )
        result.append(profile)
    return result


def get_defaults(path: Path | None = None) -> dict:
    """Get default role assignments from registry."""
    reg = load_registry(path)
    return reg.get("defaults", {})


def get_strategy(path: Path | None = None) -> str:
    """Get role assignment strategy: 'manual' or 'auto'."""
    reg = load_registry(path)
    return reg.get("role_strategy", "manual")


# ── Role Assignment ───────────────────────────────────────

def resolve_builder(
    agents: list[AgentProfile],
    contract: SkillContract,
    explicit: str | None = None,
) -> str:
    """Resolve which IDE fills the builder role.

    Priority: explicit flag > defaults > auto-pick.
    Returns agent ID string (not AgentProfile — we don't need metadata for role-based flow).
    """
    if explicit:
        return explicit

    defaults = get_defaults()
    if defaults.get("builder"):
        return defaults["builder"]

    # Auto fallback: pick by capabilities
    candidates = _eligible(agents, contract, ["implementation"])
    if candidates:
        return candidates[0].id
    raise ValueError("No agent configured for builder role")


def resolve_reviewer(
    agents: list[AgentProfile],
    contract: SkillContract,
    builder_id: str,
    explicit: str | None = None,
) -> str:
    """Resolve which IDE fills the reviewer role (must differ from builder).

    Priority: explicit flag > defaults > auto-pick.
    """
    if explicit:
        if explicit == builder_id:
            raise ValueError(
                f"Reviewer cannot be the same as builder ({builder_id}). "
                f"Cross-model adversarial review requires different IDEs."
            )
        return explicit

    defaults = get_defaults()
    default_reviewer = defaults.get("reviewer")
    if default_reviewer and default_reviewer != builder_id:
        return default_reviewer

    # Auto fallback: pick by capabilities, exclude builder
    candidates = _eligible(agents, contract, ["review"], exclude=[builder_id])
    if candidates:
        return candidates[0].id

    # Last resort: any agent that isn't the builder
    others = [a for a in agents if a.id != builder_id]
    if others:
        return others[0].id

    raise ValueError(
        f"No agent available for reviewer role (builder={builder_id}). "
        f"Add at least 2 agents to agents/agents.yaml."
    )


# ── Internal helpers ──────────────────────────────────────

def _eligible(
    agents: list[AgentProfile],
    contract: SkillContract,
    required_capabilities: list[str],
    exclude: list[str] | None = None,
) -> list[AgentProfile]:
    """Filter agents by contract compatibility and capabilities."""
    exclude = exclude or []
    candidates: list[AgentProfile] = []
    for agent in agents:
        if agent.id in exclude:
            continue
        if contract.supported_agents and agent.id not in contract.supported_agents:
            continue
        if not all(cap in agent.capabilities for cap in required_capabilities):
            continue
        candidates.append(agent)
    candidates.sort(key=lambda a: (a.reliability * a.queue_health, -a.cost), reverse=True)
    return candidates


# Legacy API kept for test compatibility
def eligible_agents(
    agents: list[AgentProfile],
    contract: SkillContract,
    required_capabilities: list[str],
    role: str = "builder",
) -> list[AgentProfile]:
    return _eligible(agents, contract, required_capabilities)


def pick_agent(
    agents: list[AgentProfile],
    contract: SkillContract,
    required_capabilities: list[str],
    role: str = "builder",
    exclude: list[str] | None = None,
) -> AgentProfile:
    candidates = _eligible(agents, contract, required_capabilities, exclude)
    if not candidates:
        raise ValueError(
            f"No eligible agent for skill={contract.id}, "
            f"caps={required_capabilities}, role={role}, exclude={exclude}"
        )
    return candidates[0]


def pick_reviewer(
    agents: list[AgentProfile],
    contract: SkillContract,
    builder_id: str,
) -> AgentProfile:
    return pick_agent(
        agents, contract, ["review"], role="reviewer", exclude=[builder_id],
    )
