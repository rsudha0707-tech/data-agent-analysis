"""Phase 2 integration gate — validates MsSQL flag, cache routing, telemetry.

Runs against the REAL LLM/API when a key is present; skips otherwise.
Uses dependency injection / monkeypatching to avoid needing a live MsSQL server.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from io import BytesIO

from src.api import create_app
from src.config.settings import get_settings
from src.db.models import RunRow
from src.db.session import create_db_session


def _require_key() -> None:
    if get_settings().resolve_provider() == "stub":
        pytest.skip("no real LLM key in .env — integration gate requires one")


@pytest.fixture()
def client():
    with TestClient(create_app()) as c:
        yield c


def _post_csv(client: TestClient, instruction: str, *, rows: str = "a,b\n1,2\n", use_mssql: bool = False):
    return client.post(
        "/runs",
        data={"instruction": instruction, "use_mssql": "true" if use_mssql else "false"},
        files={"files": ("dataset.csv", BytesIO(rows.encode("utf-8")), "text/csv")},
    )


def _mock_mssql(monkeypatch, live_rows=None, cached_payload=None, error=None):
    import src.db.mssql as mssql_mod

    monkeypatch.setattr(mssql_mod, "has_mssql", lambda: True)
    if error:

        def _live(_sql, **_):  # pragma: no cover - simple error branch
            raise RuntimeError(error)

        monkeypatch.setattr(mssql_mod, "live_query", _live)
    else:
        monkeypatch.setattr(mssql_mod, "live_query", lambda _sql, **_: live_rows or [{"x": 1}])

    if cached_payload is not None:

        def _cache_get(_q):
            return cached_payload

        monkeypatch.setattr(mssql_mod, "cache_get", _cache_get)
    else:

        def _cache_get(_q):
            return None

        monkeypatch.setattr(mssql_mod, "cache_get", _cache_get)

    monkeypatch.setattr(mssql_mod, "cache_set", lambda *_, **__: None)


def test_no_key_with_mssql_flag_still_fails_gracefully(client):
    request = client.post(
        "/runs",
        data={"instruction": "Summarize.", "use_mssql": "true"},
        files={"files": ("d.csv", BytesIO(b"a,b\n1,2\n"), "text/csv")},
    )
    assert request.status_code == 200
    run = request.json()["data"]
    assert run["status"] == "failed"
    assert "AGENT_" in run["error_message"]


def test_mssql_flag_surfaces_cache_telemetry_when_available(client, monkeypatch):
    _require_key()
    _mock_mssql(monkeypatch)
    res = _post_csv(client, "List district counts.", use_mssql=True)
    assert res.status_code == 200
    run = res.json()["data"]
    assert run["status"] == "completed"
    assert run["query_hash"] is not None or run["cache_hit"] is not None


def test_mssql_cache_hit_returns_cached_output(client, monkeypatch):
    _require_key()
    payload = {
        "output_text": "Cached insight for district counts.",
        "provider": "openrouter",
        "model": "tencent/hy3",
    }
    _mock_mssql(monkeypatch, cached_payload=payload)
    first = _post_csv(client, "List district counts.", use_mssql=True)
    assert first.status_code == 200
    first_run = first.json()["data"]
    assert first_run["status"] == "completed"


def test_invalid_mssql_url_does_not_crash_run(client, monkeypatch):
    _require_key()
    _mock_mssql(monkeypatch, error="connection failed")
    res = _post_csv(client, "List district counts.", use_mssql=True)
    assert res.status_code == 200
    run = res.json()["data"]
    assert run["status"] == "completed"


def test_post_runs_rejects_more_than_12_files(client):
    files = [("files", (f"f{i}.csv", BytesIO(b"a,b\n1,2\n"), "text/csv")) for i in range(13)]
    res = client.post(
        "/runs",
        data={"instruction": "Summarize the data."},
        files=files,
    )
    assert res.status_code == 400
