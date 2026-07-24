"""File assistant builtin agent."""
from __future__ import annotations

from src.agents.runner import AgentHubRunner


def run(payload: dict) -> dict:
    runner = AgentHubRunner()
    return runner.run("file-assistant", payload)
