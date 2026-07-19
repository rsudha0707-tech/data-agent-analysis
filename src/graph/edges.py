"""Conditional routing functions."""
from __future__ import annotations

from src.graph.state import AgentState


def after_transform(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "finalize"
