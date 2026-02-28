"""Tests for agent router."""

import pytest
from pathlib import Path

from multi_agent.router import (
    load_agents, eligible_agents, pick_agent, pick_reviewer,
    load_registry, get_defaults, get_strategy,
    resolve_builder, resolve_reviewer,
)
from multi_agent.schema import AgentProfile, SkillContract


PROFILES_PATH = Path(__file__).parent.parent / "agents" / "profiles.json"
AGENTS_YAML_PATH = Path(__file__).parent.parent / "agents" / "agents.yaml"


def _make_contract(**kwargs) -> SkillContract:
    defaults = {"id": "test-skill", "version": "1.0.0"}
    defaults.update(kwargs)
    return SkillContract(**defaults)


def _make_agents() -> list[AgentProfile]:
    return [
        AgentProfile(id="windsurf", capabilities=["implementation", "testing"]),
        AgentProfile(id="cursor", capabilities=["implementation", "review"]),
        AgentProfile(id="kiro", capabilities=["implementation", "review"]),
    ]


class TestRegistry:
    def test_load_yaml(self):
        reg = load_registry(AGENTS_YAML_PATH)
        assert reg["version"] == 2
        ids = {a["id"] for a in reg["agents"]}
        assert "windsurf" in ids
        assert "cursor" in ids

    def test_fallback_to_json(self):
        reg = load_registry(PROFILES_PATH)
        assert reg["version"] == 1
        assert reg["role_strategy"] == "auto"

    def test_get_defaults(self):
        defaults = get_defaults(AGENTS_YAML_PATH)
        assert "builder" in defaults
        assert "reviewer" in defaults

    def test_get_strategy(self):
        strategy = get_strategy(AGENTS_YAML_PATH)
        assert strategy == "manual"


class TestResolveBuilder:
    def test_explicit(self):
        agents = _make_agents()
        contract = _make_contract()
        result = resolve_builder(agents, contract, explicit="kiro")
        assert result == "kiro"

    def test_fallback_auto(self):
        agents = _make_agents()
        contract = _make_contract()
        result = resolve_builder(agents, contract)
        assert result in {"windsurf", "cursor", "kiro"}


class TestResolveReviewer:
    def test_explicit(self):
        agents = _make_agents()
        contract = _make_contract()
        result = resolve_reviewer(agents, contract, builder_id="windsurf", explicit="cursor")
        assert result == "cursor"

    def test_explicit_same_as_builder_raises(self):
        agents = _make_agents()
        contract = _make_contract()
        with pytest.raises(ValueError, match="cannot be the same"):
            resolve_reviewer(agents, contract, builder_id="cursor", explicit="cursor")

    def test_auto_differs_from_builder(self):
        agents = _make_agents()
        contract = _make_contract()
        result = resolve_reviewer(agents, contract, builder_id="windsurf")
        assert result != "windsurf"


class TestLoadAgents:
    def test_load_json(self):
        agents = load_agents(PROFILES_PATH)
        assert len(agents) == 3
        ids = {a.id for a in agents}
        assert ids == {"codex", "windsurf", "antigravity"}

    def test_load_yaml(self):
        agents = load_agents(AGENTS_YAML_PATH)
        ids = {a.id for a in agents}
        assert "windsurf" in ids
        assert "cursor" in ids


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
