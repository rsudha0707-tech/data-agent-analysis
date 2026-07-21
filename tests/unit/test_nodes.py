"""Unit tests for graph nodes — analyze_data routing, cache hit/miss, and error paths."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.graph.nodes import analyze_data, handle_error
from src.graph.state import AgentState
from src.llm.providers.base import LLMError


def _state(**kwargs) -> AgentState:
    base: AgentState = {
        "run_id": "run-1",
        "input_text": "data",
        "instruction": "Count rows",
        "error": None,
        "file_count": 1,
        "use_mssql": False,
        "cache_hit": None,
        "query_hash": None,
    }
    base.update(kwargs)
    return base


def test_analyze_data_cache_hit_returns_cached(monkeypatch):
    monkeypatch.setattr("src.graph.nodes.has_mssql", lambda: True)
    monkeypatch.setattr("src.graph.nodes.cache_get", lambda _q: {
        "output_text": "cached answer",
        "provider": "openrouter",
        "model": "m",
    })
    monkeypatch.setattr("src.graph.nodes.cache_set", lambda *_, **__: None)
    monkeypatch.setattr("src.graph.nodes.live_query", lambda *_a, **__: [{"x": 1}])
    out = analyze_data(_state(use_mssql=True, instruction="Count rows"))
    assert out["status"] == "completed"
    assert out["output_text"] == "cached answer"
    assert out["cache_hit"] is True
    assert out["provider"] == "openrouter"
    assert out["model"] == "m"
    assert "query_hash" in out


def test_analyze_data_cache_miss_invokes_llm(monkeypatch):
    monkeypatch.setattr("src.graph.nodes.has_mssql", lambda: True)
    monkeypatch.setattr("src.graph.nodes.cache_get", lambda _q: None)
    monkeypatch.setattr("src.graph.nodes.live_query", lambda _sql, **_: [{"x": 1}])
    monkeypatch.setattr("src.graph.nodes.cache_set", lambda *_, **__: None)

    fake_client = MagicMock()
    fake_client.provider_name = "openrouter"
    fake_client.model = "m"
    fake_client.complete.return_value = "live answer"

    with patch("src.graph.nodes.LLMClient", return_value=fake_client), patch(
        "src.graph.nodes.load_prompt", return_value="system"
    ):
        out = analyze_data(_state(use_mssql=True, instruction="Count rows"))

    assert out["status"] == "completed"
    assert out["output_text"] == "live answer"
    assert out["cache_hit"] is False
    assert "query_hash" in out


def test_analyze_data_llm_error_returns_failed(monkeypatch):
    fake_client = MagicMock()
    fake_client.provider_name = "openrouter"
    fake_client.model = "m"
    fake_client.complete.side_effect = LLMError("boom")

    with patch("src.graph.nodes.LLMClient", return_value=fake_client), patch(
        "src.graph.nodes.load_prompt", return_value="system"
    ):
        out = analyze_data(_state())

    assert out["status"] == "failed"
    assert "boom" in (out.get("error") or "")


def test_handle_error_sets_status():
    out = handle_error(_state())
    assert out["status"] == "failed"