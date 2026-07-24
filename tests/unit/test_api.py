from fastapi.testclient import TestClient

from src.api import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_health_reports_provider_presence_only(no_keys):
    with _client() as client:
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["status"] == "ok"
        assert data["key_configured"] is False
        assert "api_key" not in res.text.lower()


def test_get_unknown_run_is_404():
    with _client() as client:
        res = client.get("/runs/nope")
        assert res.status_code == 404
        assert res.json()["detail"]["code"] == "run_not_found"


def test_create_run_rejects_more_than_12_files(no_keys):
    with _client() as client:
        from io import BytesIO

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


def test_create_run_accepts_json_payload_without_files(no_keys, monkeypatch):
    import src.agents.runner as agent_runner
    from src.llm.providers.base import LLMProvider

    class FakeProvider(LLMProvider):
        name = "test"
        model = "test-model"

        def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
            return '{"insight": "ok", "table_summary": "ok", "chart_spec": {"type": "bar", "x": "a", "y": "b", "label": "Fake"}}'

    monkeypatch.setattr(agent_runner, "create_llm_provider", lambda: FakeProvider())

    with _client() as client:
        res = client.post(
            "/runs",
            json={"instruction": "Draft a finding", "extra": "ok"},
        )
        assert res.status_code == 200
        run = res.json()["data"]
        assert run["status"] == "completed"
        assert run["output_text"]


def test_list_runs_returns_envelope(no_keys):
    with _client() as client:
        res = client.get("/runs")
        assert res.status_code == 200
        assert isinstance(res.json()["data"], list)


def test_run_without_key_fails_gracefully(no_keys):
    with _client() as client:
        from io import BytesIO
        res = client.post(
            "/runs",
            data={"instruction": "Summarize the data."},
            files={"files": ("data.csv", BytesIO(b"a,b\n1,2\n"), "text/csv")},
        )
        assert res.status_code == 200
        run = res.json()["data"]
        assert run["status"] == "failed"
        assert "error_message" in run


def test_frontend_served_at_app():
    with _client() as client:
        res = client.get("/app/")
        assert res.status_code == 200
        assert "CrimAnalyze" in res.text
        assert "styles.css" in res.text
        assert "app.js" in res.text
