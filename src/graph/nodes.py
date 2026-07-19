"""Graph nodes — THE CAPABILITY SLOT.

``transform_text`` is the baseline capability: it applies the user's
instruction to the input text with one batched LLM call. When building your
agent, replace this node (and src/prompts/transform.md, and the frontend form)
with your capability — the graph wiring, API, and DB stay as they are.

Node contract: ``(state) -> partial state``; put failures in ``error`` so the
error edge routes to handle_error — never raise through the graph.
"""
from __future__ import annotations

from src.graph.state import AgentState
from src.llm.client import LLMClient, load_prompt
from src.llm.providers.base import LLMError


def transform_text(state: AgentState) -> AgentState:
    """Apply the instruction to the input text — ONE batched LLM call.

    Never loop an LLM call per output line/token: generate the whole artifact
    in one call and split downstream if needed (cost blows up otherwise).
    """
    try:
        client = LLMClient()
        system = load_prompt("transform")
        user = (
            f"INSTRUCTION:\n{state['instruction']}\n\n"
            f"TEXT:\n{state['input_text']}"
        )
        output = client.complete(system, user, max_tokens=2048)
        return {
            "output_text": output,
            "provider": client.provider_name,
            "model": client.model,
            "error": None,
        }
    except LLMError as exc:
        return {"error": str(exc)}


def handle_error(state: AgentState) -> AgentState:
    return {"status": "failed"}


def finalize(state: AgentState) -> AgentState:
    return {"status": "completed"}
