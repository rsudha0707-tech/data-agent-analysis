"""Graph nodes — Phase 1 capability: analyze_data."""
from __future__ import annotations

from src.graph.state import AgentState
from src.llm.client import LLMClient, load_prompt
from src.llm.providers.base import LLMError


def analyze_data(state: AgentState) -> AgentState:
    """Analyze uploaded CSVs using one real LLM call; input is a schema + row summaries."""
    try:
        client = LLMClient()
        system = load_prompt("analyze")
        output = client.complete(system, state["input_text"], max_tokens=2048)
        return {
            "output_text": output,
            "provider": client.provider_name,
            "model": client.model,
            "file_count": int(state.get("file_count") or 0),
            "error": None,
        }
    except LLMError as exc:
        return {"error": str(exc)}


def handle_error(state: AgentState) -> AgentState:
    return {"status": "failed"}


def finalize(state: AgentState) -> AgentState:
    return {"status": "completed"}
