"""Phase 2 integration-style tests — _no_ real LLM/network needed."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from io import BytesIO

from src.api import create_app
from src.db.models import RunRow
from src.db.session import create_db_session


def _client() -> TestClient:
    return TestClient(create_app())


def test_list_runs_returns_envelope(no_keys) -> None:
    with _client() as client:
        res = client.get("/runs")
        assert res.status_code == 200
        assert isinstance(res.json()["data"], list)


def test_get_unknown_run_is_404(no_keys) -> None:
    with _client() as client:
        res = client.get("/runs/nope")
        assert res.status_code == 404
        assert res.json()["detail"]["code"] == "run_not_found"


def test_run_without_key_fails_gracefully(no_keys) -> None:
    with _client() as client:
        res = client.post(
            "/runs",
            data={"instruction": "Summarize.", "use_mssql": "true"},
            files={"files": ("d.csv", BytesIO(b"a,b\n1,2\n"), "text/csv")},
        )
        assert res.status_code == 200
        run = res.json()["data"]
        assert run["status"] == "failed"
        assert "error_message" in run


def test_create_run_rejects_more_than_12_files(no_keys) -> None:
    with _client() as client:
        files = [
            ("files", (f"f{i}.csv", BytesIO(b"a,b\n1,2\n"), "text/csv"))
            for i in range(13)
        ]
        res = client.post(
            "/runs",
            data={"instruction": "Summarize the data."},
            files=files,
        )
        assert res.status_code == 400


def test_mock_mssql_cache_hit_returns_cached_output(no_keys, monkeypatch) -> None:
    import src.graph.nodes as nodes_mod

    monkeypatch.setattr(nodes_mod, "has_mssql", lambda: True)
    monkeypatch.setattr(nodes_mod, "cache_get", lambda _q: {
        "output_text": "cached",
        "provider": "openrouter",
        "model": "m",
    })
    monkeypatch.setattr(nodes_mod, "cache_set", lambda *_, **__: None)

    out = nodes_mod.analyze_data({
        "run_id": "run-x",
        "input_text": "data",
        "instruction": "Count rows",
        "error": None,
        "file_count": 1,
        "use_mssql": True,
        "cache_hit": None,
        "query_hash": None,
    })
    assert out["status"] == "completed"
    assert out["output_text"] == "cached"
    assert out["cache_hit"] is True
    assert "query_hash" in out


def test_mock_mssql_cache_miss_invokes_provider_stub_as_failure(no_keys, monkeypatch) -> None:
    import src.db.mssql as mssql_mod
    import src.graph.nodes as nodes_mod

    monkeypatch.setattr(mssql_mod, "has_mssql", lambda: True)
    monkeypatch.setattr(mssql_mod, "cache_get", lambda _q: None)
    monkeypatch.setattr(mssql_mod, "live_query", lambda _sql, **_: [{"x": 1}])
    monkeypatch.setattr(mssql_mod, "cache_set", lambda *_, **__: None)

    out = nodes_mod.analyze_data({
        "run_id": "run-y",
        "input_text": "data",
        "instruction": "Count rows",
        "error": None,
        "file_count": 1,
        "use_mssql": True,
        "cache_hit": None,
        "query_hash": None,
    })
    assert out["status"] == "failed"
    assert "error" in out


def test_history_open_button_loads_individual_run(no_keys) -> None:
    with _client() as client:
        res = client.post(
            "/runs",
            data={"instruction": "Spreadsheet X"},
            files={"files": ("d.csv", BytesIO(b"a,b\n1,2\n"), "text/csv")},
        )
        assert res.status_code == 200
        run_id = res.json()["data"]["run_id"]

        res2 = client.get(f"/runs/{run_id}")
        assert res2.status_code == 200
        run = res2.json()["data"]
        assert run["run_id"] == run_id
        assert "created_at" in run
        assert "updated_at" in run
        assert isinstance(run["file_count"], int)
        assert run["cache_hit"] is None or isinstance(run["cache_hit"], bool)
