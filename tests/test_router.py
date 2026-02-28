"""Tests for agent router."""

import pytest
from pathlib import Path

from multi_agent.router import load_agents, eligible_agents, pick_agent, pick_reviewer
from multi_agent.schema import AgentProfile, SkillContract


PROFILES_PATH = Path(__file__).parent.parent / "agents" / "profiles.json"


def _make_contract(**kwargs) -> SkillContract:
    defaults = {"id": "test-skill", "version": "1.0.0"}
    defaults.update(kwargs)
    return SkillContract(**defaults)


class TestLoadAgents:
    def test_load(self):
        agents = load_agents(PROFILES_PATH)
        assert len(agents) == 3
        ids = {a.id for a in agents}
        assert ids == {"codex", "windsurf", "antigravity"}


class TestEligible:
    def test_all_eligible(self):
        agents = load_agents(PROFILES_PATH)
        contract = _make_contract(supported_agents=["codex", "windsurf", "antigravity"])
        result = eligible_agents(agents, contract, ["implementation"])
        # antigravity has implementation capability
        ids = {a.id for a in result}
        assert "windsurf" in ids
        assert "codex" in ids

    def test_filter_by_supported(self):
        agents = load_agents(PROFILES_PATH)
        contract = _make_contract(supported_agents=["windsurf"])
        result = eligible_agents(agents, contract, ["implementation"])
        assert len(result) == 1
        assert result[0].id == "windsurf"

    def test_filter_by_capability(self):
        agents = load_agents(PROFILES_PATH)
        contract = _make_contract(supported_agents=[])
        result = eligible_agents(agents, contract, ["security"])
        # Only antigravity has security
        assert len(result) == 1
        assert result[0].id == "antigravity"


class TestPickAgent:
    def test_pick_builder(self):
        agents = load_agents(PROFILES_PATH)
        contract = _make_contract(supported_agents=["codex", "windsurf", "antigravity"])
        agent = pick_agent(agents, contract, ["implementation"], role="builder")
        assert agent.id in {"codex", "windsurf", "antigravity"}

    def test_pick_with_exclude(self):
        agents = load_agents(PROFILES_PATH)
        contract = _make_contract(supported_agents=["codex", "windsurf", "antigravity"])
        agent = pick_agent(
            agents, contract, ["implementation"], role="builder", exclude=["windsurf"]
        )
        assert agent.id != "windsurf"

    def test_no_eligible(self):
        agents = load_agents(PROFILES_PATH)
        contract = _make_contract(supported_agents=["nonexistent"])
        with pytest.raises(ValueError, match="No eligible agent"):
            pick_agent(agents, contract, ["implementation"])


class TestPickReviewer:
    def test_reviewer_differs_from_builder(self):
        agents = load_agents(PROFILES_PATH)
        contract = _make_contract(supported_agents=["codex", "windsurf", "antigravity"])
        reviewer = pick_reviewer(agents, contract, builder_id="windsurf")
        assert reviewer.id != "windsurf"
        assert "review" in reviewer.capabilities
