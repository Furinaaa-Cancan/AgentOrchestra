"""Agent router — select the best agent for a given task and skill contract."""

from __future__ import annotations

import json
from pathlib import Path

from multi_agent.config import agents_profile_path
from multi_agent.schema import AgentProfile, SkillContract


def load_agents(path: Path | None = None) -> list[AgentProfile]:
    """Load agent profiles from profiles.json."""
    path = path or agents_profile_path()
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return [AgentProfile(**a) for a in data["agents"]]


def eligible_agents(
    agents: list[AgentProfile],
    contract: SkillContract,
    required_capabilities: list[str],
    role: str = "builder",
) -> list[AgentProfile]:
    """Filter agents by contract.supported_agents and required capabilities."""
    candidates: list[AgentProfile] = []
    for agent in agents:
        if contract.supported_agents and agent.id not in contract.supported_agents:
            continue
        if not all(cap in agent.capabilities for cap in required_capabilities):
            continue
        candidates.append(agent)
    return candidates


def pick_agent(
    agents: list[AgentProfile],
    contract: SkillContract,
    required_capabilities: list[str],
    role: str = "builder",
    exclude: list[str] | None = None,
) -> AgentProfile:
    """Pick the best eligible agent (highest reliability * queue_health, lowest cost)."""
    exclude = exclude or []
    candidates = [
        a for a in eligible_agents(agents, contract, required_capabilities, role)
        if a.id not in exclude
    ]
    if not candidates:
        raise ValueError(
            f"No eligible agent for skill={contract.id}, "
            f"caps={required_capabilities}, role={role}, exclude={exclude}"
        )
    # Score: higher is better
    candidates.sort(key=lambda a: (a.reliability * a.queue_health, -a.cost), reverse=True)
    return candidates[0]


def pick_reviewer(
    agents: list[AgentProfile],
    contract: SkillContract,
    builder_id: str,
) -> AgentProfile:
    """Pick a reviewer agent — must differ from builder (cross-model adversarial review)."""
    review_caps = ["review"]
    return pick_agent(
        agents, contract, review_caps, role="reviewer", exclude=[builder_id],
    )
