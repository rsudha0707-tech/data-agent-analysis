"""Tests for multi-agent registry and runner."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.agents.registry import AgentManifest, AgentRegistry
from src.agents.runner import AgentHubRunner
from src.llm.providers.base import LLMProvider


class FakeProvider(LLMProvider):
    name = "test-provider"
    model = "test-model"

    def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
        return '{"insight": "fake insight", "table_summary": "summary", "chart_spec": {"type": "bar", "x": "a", "y": "b", "label": "Fake"}}'


@pytest.fixture()
def registry(tmp_path: Path) -> AgentRegistry:
    configs_dir = tmp_path / "agents"
    configs_dir.mkdir(parents=True, exist_ok=True)
    return AgentRegistry(configs_dir)


def test_list_agents_empty(registry: AgentRegistry) -> None:
    assert registry.list_agents() == []


def test_load_agent_manifest(registry: AgentRegistry) -> None:
    yaml_text = """
name: Test Agent
description: A test agent.
prompt_template: "Hello {{INSTRUCTION}}"
input_schema:
  type: object
  required: [instruction]
  properties:
    instruction:
      type: string
tools:
  - tool_x
entrypoint:
  module: x.y
  symbol: z
config:
  max_files: 1
"""
    (registry._configs_dir / "test.yaml").write_text(yaml_text, encoding="utf-8")
    manifest = registry.load("test")
    assert manifest.agent_id == "test"
    assert manifest.name == "Test Agent"
    assert manifest.tools == ["tool_x"]
    assert manifest.config == {"max_files": 1}


def test_registry_caches_manifest(registry: AgentRegistry) -> None:
    yaml_text = "name: Cache\nprompt_template: ''\ntools: []\nentrypoint:\n  module: x.y\n  symbol: z\nconfig: {}\n"
    path = registry._configs_dir / "cache.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    registry.load("cache")
    assert len(registry._cache) == 1
    registry.load("cache")
    assert len(registry._cache) == 1


def test_runner_completes_with_structured_output(no_keys, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir("C:/Users/Admin/data-agent-analysis")
    manifest = AgentManifest(
        agent_id="web-researcher",
        name="Web Researcher",
        description="",
        prompt_template="You are a careful research assistant.\n\nQuestion:\n{{INSTRUCTION}}",
        input_schema={},
        tools=["drafting"],
        entrypoint_module="src.agents.builtin.web_researcher_agent",
        entrypoint_symbol="run",
        config={},
    )
    registry = AgentRegistry(Path("config/agents"))
    registry._cache["web-researcher"] = manifest

    monkeypatch.setattr("src.agents.runner.create_llm_provider", lambda: FakeProvider(), raising=False)
    runner = AgentHubRunner(registry)
    result = runner.run("web-researcher", {
        "instruction": "Summarize project goals in 2 bullets.",
        "context": "Phase A rebuild specifies a configurable multi-agent product.",
    })
    assert result["status"] == "completed"
    assert result["agent_id"] == "web-researcher"
    assert isinstance(result["output"], str)
    assert len(result["output"]) > 0

    parsed = result["payload"]["structured"]
    assert isinstance(parsed, dict)
    assert parsed["insight"] == "fake insight"
    assert parsed["chart_spec"]["type"] == "bar"

    assert result["provider"] == "test-provider"
    assert result["model"] == "test-model"
    assert "tools_used" in result
    assert result["tools_used"] == ["drafting"]
