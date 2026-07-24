"""Application settings — Pydantic BaseSettings, env prefix ``AGENT_``."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Provider defaults used when AGENT_LLM_MODEL is blank.
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "gemini": "gemini-2.5-flash",
    "openrouter": "tencent/hy3",  # cheap default — override via AGENT_LLM_MODEL
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(default="sqlite:///./data/app.db")
    llm_provider: str = Field(default="auto")
    llm_model: str = Field(default="")
    anthropic_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")
    openrouter_api_key: str = Field(default="")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")
    log_level: str = Field(default="INFO")
    database_url_mssql: str = Field(default="")
    active_agent_id: str = Field(default="")

    # Multi-agent product paths
    agent_configs_dir: Path = Field(default=Path("config/agents"))

    # ----- derived -----
    def resolve_provider(self) -> str:
        p = (self.llm_provider or "auto").strip().lower()
        if p != "auto":
            return p
        if self.anthropic_api_key:
            return "anthropic"
        if self.gemini_api_key:
            return "gemini"
        if self.openrouter_api_key:
            return "openrouter"
        return "stub"

    def resolve_model(self) -> str:
        if self.llm_model:
            return self.llm_model
        return DEFAULT_MODELS.get(self.resolve_provider(), "")

    def active_agent_path(self) -> Path:
        base = self.agent_configs_dir
        if self.active_agent_id:
            candidate = base / f"{self.active_agent_id}.yaml"
            if candidate.exists():
                return candidate
        # fallback: first available agent config
        if base.exists():
            for p in sorted(base.glob("*.yaml")):
                return p
        raise FileNotFoundError(f"No agent configs found in {base}")


_settings: Settings | None = None


def get_settings(**overrides) -> Settings:
    global _settings
    if _settings is None or overrides:
        _settings = Settings(**overrides)
    return _settings
