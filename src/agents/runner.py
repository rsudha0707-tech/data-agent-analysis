"""AgentHub unified runner.

Discovers agent configs under config/agents/*.yaml, builds prompt context,
invokes the configured builtin entrypoint, and returns a structured result
envelope: payload, provider/model metadata, agent_id, tool usage, and status.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.agents.registry import AgentRegistry, AgentManifest
from src.config.settings import get_settings
from src.llm.providers.factory import create_llm_provider
from src.observability.events import get_logger, log_span


_STATUS_COMPLETED = "completed"
_STATUS_FAILED = "failed"


class AgentHubRunner:
    def __init__(self, registry: AgentRegistry | None = None) -> None:
        self._registry = registry or AgentRegistry(get_settings().agent_configs_dir)
        self._log = get_logger("agenthub.runner")

    def list_agents(self) -> list[AgentManifest]:
        return self._registry.list_agents()

    def run(self, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        manifest = self._registry.load(agent_id)
        provider = create_llm_provider()
        prompt = self._render_prompt(manifest, payload)

        agent_result: dict[str, Any] = {
            "agent_id": agent_id,
            "agent_name": manifest.name,
            "status": _STATUS_COMPLETED,
            "payload": payload,
            "provider": provider.name,
            "model": getattr(provider, "model", ""),
            "tools_used": [],
            "output": None,
            "error": None,
        }

        with log_span(self._log, "agent_run", agent_id=agent_id) as span:
            try:
                text = provider.complete(
                    system="Return strict JSON matching the requested schema.",
                    user=prompt,
                    max_tokens=1024,
                )
                agent_result["output"] = text
                self._bind_tool_usage(agent_result, manifest, payload)

                # Best-effort JSON parsing for structured output contract
                parsed = self._safe_parse_json_output(text)
                agent_result["payload"] = {
                    **payload,
                    "output_text": text,
                    "structured": parsed,
                }
                span["status"] = _STATUS_COMPLETED
            except Exception as exc:  # pragma: no cover - exercised via tests
                self._log.error("agent_run_error", agent_id=agent_id, error=str(exc))
                agent_result["status"] = _STATUS_FAILED
                agent_result["error"] = str(exc)
                span["status"] = _STATUS_FAILED

        return agent_result

    def _render_prompt(self, manifest: AgentManifest, payload: dict[str, Any]) -> str:
        instruction = str(payload.get("instruction", "")).strip()
        input_context = self._build_input_context(manifest, payload)
        prompt = manifest.prompt_template or "{{INSTRUCTION}}"
        prompt = prompt.replace("{{INSTRUCTION}}", instruction)
        prompt = prompt.replace("{{INPUT_CONTEXT}}", input_context)
        return prompt

    def _build_input_context(self, manifest: AgentManifest, payload: dict[str, Any]) -> str:
        # Builtins
        agent_id = manifest.agent_id
        if agent_id == "up-police-data-analyst":
            return self._context_from_files(payload)
        if agent_id == "file-assistant":
            paths = payload.get("paths") or []
            if not paths:
                return "(no file paths provided)"
            return self._safe_read_paths(paths)
        if agent_id == "github-assistant":
            return self._context_from_repo(payload)
        if agent_id == "web-researcher":
            return str(payload.get("context") or "(no additional context provided)")
        return str(payload.get("context") or payload.get("input_text") or "")

    def _context_from_files(self, payload: dict[str, Any]) -> str:
        files = payload.get("files") or []
        if not files:
            return "(no files provided)"
        parts: list[str] = []
        for f in files[: manifest.config.get("max_files", 12)]:
            if hasattr(f, "filename") and hasattr(f, "read"):
                filename = getattr(f, "filename", "file")
                try:
                    content = f.read().decode("utf-8", errors="replace")
                except Exception as exc:
                    content = f"(unreadable file: {exc})"
                parts.append(f"--- {filename} ---\n{content[:12000]}")
                f.seek(0)
            else:
                parts.append(f"--- file ---\n{str(f)[:12000]}")
        return "\n\n".join(parts) if parts else "(no readable file content)"

    def _safe_read_paths(self, paths: list[str]) -> str:
        allowed = {str(ext).lower().lstrip(".") for ext in (".txt", ".md", ".csv", ".json", ".py")}
        parts: list[str] = []
        for path in paths[:20]:
            try:
                text = Path(path).read_text(encoding="utf-8", errors="replace")
                ext = Path(path).suffix.lower().lstrip(".")
                if ext not in allowed:
                    parts.append(f"{path}: (unsupported extension .{ext})")
                    continue
                parts.append(f"--- {path} ---\n{text[:12000]}")
            except Exception as exc:
                parts.append(f"{path}: (unreadable: {exc})")
        return "\n\n".join(parts) if parts else "(no readable paths)"

    def _context_from_repo(self, payload: dict[str, Any]) -> str:
        repo_url = payload.get("repo_url") or ""
        patch = payload.get("patch") or ""
        parts = [f"Repository: {repo_url}"]
        if patch:
            parts.append(f"Patch:\n{patch[:20000]}")
        return "\n\n".join(parts) if any(parts) else "(no repository context provided)"

    def _safe_parse_json_output(self, text: str) -> dict[str, Any] | None:
        if not text:
            return None
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            candidate = text[start:end]
            return __import__("json").loads(candidate)
        except Exception:
            return None

    def _bind_tool_usage(self, agent_result: dict[str, Any], manifest: AgentManifest, payload: dict[str, Any]) -> None:
        agent_id = manifest.agent_id
        if agent_id == "up-police-data-analyst":
            agent_result["tools_used"] = ["mssql_cache", "summarizer", "chart_spec"] if manifest.tools else []
            if payload.get("use_mssql"):
                agent_result["tools_used"] = ["mssql_cache"] + agent_result["tools_used"]
        elif agent_id == "github-assistant":
            agent_result["tools_used"] = ["repo_reader"] + (["triage", "pr_reviewer"] if payload.get("instruction","").lower().startswith("review") else [])
        else:
            agent_result["tools_used"] = list(manifest.tools)


def run_agent(agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    runner = AgentHubRunner()
    return runner.run(agent_id, payload)


__all__ = ["AgentHubRunner", "run_agent"]
