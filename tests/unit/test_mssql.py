"""Unit tests for src.db.mssql — cache and has_mssql behavior without a live DB."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3

import pytest

from src.db import mssql as mssql_mod


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(mssql_mod, "_CACHE_DIR", tmp_path)


def test_has_mssql_false_when_no_url(monkeypatch):
    monkeypatch.setattr(mssql_mod, "_mssql_url", lambda: None)
    assert mssql_mod.has_mssql() is False


def test_cache_set_get_roundtrip(tmp_path, monkeypatch):
    db_path = tmp_path / "cache.sqlite3"
    monkeypatch.setattr(mssql_mod, "_cache_db_path", lambda: db_path)
    mssql_mod.cache_set("q1", {"output_text": "ok"}, ttl_seconds=60)
    row = mssql_mod.cache_get("q1")
    assert row["output_text"] == "ok"


def test_cache_get_miss_returns_none():
    assert mssql_mod.cache_get("missing") is None


def test_cache_ttl_expiry(tmp_path, monkeypatch):
    db_path = tmp_path / "cache2.sqlite3"
    monkeypatch.setattr(mssql_mod, "_cache_db_path", lambda: db_path)
    # Write a backdated cache row directly to simulate expiry.
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, data TEXT, expires_at TEXT)"
    )
    past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=10)).isoformat()
    conn.execute(
        "REPLACE INTO cache (key, data, expires_at) VALUES (?, ?, ?)",
        ("expired-key", json.dumps({"output_text": "stale"}), past),
    )
    conn.commit()
    conn.close()

    assert mssql_mod.cache_get("expired-key") is None