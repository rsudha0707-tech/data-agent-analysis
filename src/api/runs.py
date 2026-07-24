"""Runs API — POST /runs executes the agent; GET /runs/{id} fetches a run."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from src.api._common import api_error, ok
from src.agents.runner import AgentHubRunner, run_agent
from src.config.settings import get_settings
from src.db.models import RunRow
from src.db.session import get_session
from src.domain import RunResult
from src.graph.runner import run_agent as legacy_run_agent
from src.summarizer import summarize_files


router = APIRouter()


def _to_result(run: RunRow) -> RunResult:
    return RunResult(
        run_id=run.id,
        status=run.status,
        output_text=run.output_text,
        provider=run.provider,
        model=run.model,
        error_message=run.error_message,
        file_count=getattr(run, "file_count", 0) or 0,
        cache_hit=getattr(run, "cache_hit", None),
        query_hash=getattr(run, "query_hash", None),
    )


@router.post("/runs")
def create_run(
    request: Request,
    instruction: str = Form(default="Summarize the data and answer the question."),
    use_mssql: bool = Form(default=False),
    agent_id: str = Form(default=""),
    files: List[UploadFile] = File(default=[]),
    session: Session = Depends(get_session),
) -> dict:
    if not instruction or not instruction.strip():
        raise api_error("validation_error", "instruction is required", 400)

    agent_id = (agent_id or "").strip() or get_settings().active_agent_path().stem

    if len(files) > 12:
        raise api_error("validation_error", "maximum 12 files per run", 400)

    if files:
        prepared_inputs: list[tuple[str, bytes]] = []
        total_bytes = 0
        for f in files:
            raw = f.file.read()
            total_bytes += len(raw)
            prepared_inputs.append((f.filename or "upload", raw))
        if total_bytes > 5_000_000:
            raise api_error(
                "validation_error",
                f"total input exceeds 5MB ({total_bytes} bytes)",
                400,
            )

        input_text, file_count = summarize_files(
            [n for n, _ in prepared_inputs],
            [c for _, c in prepared_inputs],
        )

        run_id = legacy_run_agent(
            input_text,
            instruction.strip(),
            file_count=file_count,
            use_mssql=use_mssql,
        )
    else:
        payload = {
            "instruction": instruction.strip(),
            "use_mssql": use_mssql,
        }
        try:
            raw = getattr(request, "_body", None)
            if raw is None:
                raw = request.body()
        except Exception:
            raw = b"{}"
        try:
            extra = json.loads(raw.decode("utf-8") or "{}")
            payload.update({k: v for k, v in extra.items() if k not in payload})
        except Exception:
            pass

        result = run_agent(agent_id, payload)
        run = RunRow(
            status=result["status"],
            input_text=json.dumps(payload)[:4000],
            instruction=payload.get("instruction", ""),
            output_text=result.get("output"),
            provider=result.get("provider"),
            model=result.get("model"),
            error_message=result.get("error"),
        )
        session.add(run)
        session.flush()
        run_id = run.id

    run = session.get(RunRow, run_id)
    if run is None:
        raise api_error("run_not_found", f"run {run_id} vanished", 500)
    return ok(_to_result(run).model_dump())


@router.get("/runs/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = session.get(RunRow, run_id)
    if run is None:
        raise api_error("run_not_found", f"no run with id {run_id}", 404)
    return ok(_to_result(run).model_dump())


@router.get("/runs")
def list_runs(session: Session = Depends(get_session)) -> dict:
    runs = (
        session.query(RunRow)
        .order_by(RunRow.updated_at.desc())
        .limit(50)
        .all()
    )
    return ok([_to_result(run).model_dump() for run in runs])


@router.get("/agents")
def list_agents() -> dict:
    registry = AgentHubRunner()._registry
    manifests = registry.list_agents()
    return ok(
        [
            {
                "agent_id": m.agent_id,
                "name": m.name,
                "description": m.description,
                "tools": m.tools,
            }
            for m in manifests
        ]
    )
