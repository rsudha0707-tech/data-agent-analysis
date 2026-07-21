"""Unit tests for provider selection and fallback contracts."""
from __future__ import annotations

import pytest

from src.config.settings import get_settings
from src.llm.providers.anthropic import AnthropicProvider
from src.llm.providers.gemini import GeminiProvider
from src.llm.providers.openrouter import OpenRouterProvider
from src.llm.providers.factory import create_llm_provider


def test_no_key_resolves_to_stub(no_keys):
    s = get_settings()
    assert s.resolve_provider() == "stub"
    assert s.resolve_model() == ""


def test_explicit_openrouter_with_model(no_keys, monkeypatch):
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("AGENT_LLM_MODEL", "custom/model")
    monkeypatch.setenv("AGENT_OPENROUTER_API_KEY", "test-key-not-real")
    s = get_settings()
    assert s.resolve_provider() == "openrouter"
    assert s.resolve_model() == "custom/model"


def test_explicit_gemini_model_override(no_keys, monkeypatch):
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("AGENT_LLM_MODEL", "gemini-2.0-flash-lite")
    monkeypatch.setenv("AGENT_GEMINI_API_KEY", "test-key-not-real")
    s = get_settings()
    assert s.resolve_provider() == "gemini"
    assert s.resolve_model() == "gemini-2.0-flash-lite"


def test_explicit_anthropic_model_override(no_keys, monkeypatch):
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENT_LLM_MODEL", "claude-test")
    monkeypatch.setenv("AGENT_ANTHROPIC_API_KEY", "test-key-not-real")
    s = get_settings()
    assert s.resolve_provider() == "anthropic"
    assert s.resolve_model() == "claude-test"


def test_auto_picks_openrouter_when_only_openrouter_key(no_keys, monkeypatch):
    monkeypatch.setenv("AGENT_OPENROUTER_API_KEY", "test-key-not-real")
    s = get_settings()
    assert s.resolve_provider() == "openrouter"


def test_auto_picks_gemini_when_only_gemini_key(no_keys, monkeypatch):
    monkeypatch.setenv("AGENT_GEMINI_API_KEY", "test-key-not-real")
    s = get_settings()
    assert s.resolve_provider() == "gemini"


def test_auto_picks_anthropic_when_only_anthropic_key(no_keys, monkeypatch):
    monkeypatch.setenv("AGENT_ANTHROPIC_API_KEY", "test-key-not-real")
    s = get_settings()
    assert s.resolve_provider() == "anthropic"


def test_provider_factory_respects_explicit_selection(no_keys, monkeypatch):
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("AGENT_OPENROUTER_API_KEY", "test-key-not-real")
    provider = create_llm_provider()
    assert isinstance(provider, OpenRouterProvider)
    assert provider.name == "openrouter"


def test_provider_factory_gemini_path(no_keys, monkeypatch):
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("AGENT_GEMINI_API_KEY", "test-key-not-real")
    provider = create_llm_provider()
    assert isinstance(provider, GeminiProvider)
    assert provider.name == "gemini"


def test_provider_factory_anthropic_path(no_keys, monkeypatch):
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENT_ANTHROPIC_API_KEY", "test-key-not-real")
    provider = create_llm_provider()
    assert isinstance(provider, AnthropicProvider)
    assert provider.name == "anthropic"


def test_default_models_defined_for_explicit_providers(no_keys, monkeypatch):
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "auto")
    monkeypatch.setenv("AGENT_OPENROUTER_API_KEY", "test-key-not-real")
    s = get_settings()
    assert s.resolve_model() != ""