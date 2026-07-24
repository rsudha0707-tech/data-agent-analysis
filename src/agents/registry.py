"""Multi-agent runtime registry."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.observability.events import get_logger


@dataclass(frozen=True)
class AgentManifest:
    agent_id: str
    name: str
    description: str
    prompt_template: str
    input_schema: dict[str, Any]
    tools: list[str]
    entrypoint_module: str
    entrypoint_symbol: str
    config: dict[str, Any]


class AgentRegistry:
    def __init__(self, configs_dir: Path) -> None:
        self._configs_dir = configs_dir
        self._cache: dict[str, AgentManifest] = {}
        self._log = get_logger("agent.registry")

    def load(self, agent_id: str) -> AgentManifest:
        if agent_id in self._cache:
            return self._cache[agent_id]
        path = self._configs_dir / f"{agent_id}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"agent config not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        manifest = AgentManifest(
            agent_id=agent_id,
            name=data.get("name", agent_id),
            description=data.get("description", ""),
            prompt_template=data.get("prompt_template", ""),
            input_schema=data.get("input_schema", {}),
            tools=data.get("tools", []),
            entrypoint_module=data.get("entrypoint", {}).get("module", ""),
            entrypoint_symbol=data.get("entrypoint", {}).get("symbol", ""),
            config=data.get("config", {}),
        )
        self._cache[agent_id] = manifest
        self._log.info("agent_loaded", agent_id=agent_id, manifest_name=manifest.name)
        return manifest

    def list_agents(self) -> list[AgentManifest]:
        manifests: list[AgentManifest] = []
        if not self._configs_dir.exists():
            return manifests
        for path in sorted(self._configs_dir.glob("*.yaml")):
            agent_id = path.stem
            manifests.append(self.load(agent_id))
        return manifests
