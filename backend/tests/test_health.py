from contextlib import contextmanager

from sqlalchemy.exc import OperationalError

from app.api.routes import health


def test_root_returns_api_discovery_information(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["health"] == "/api/v1/health/live"


def test_liveness_does_not_require_database(client) -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_readiness_returns_ready_when_database_query_succeeds(client, monkeypatch) -> None:
    class FakeConnection:
        def execute(self, _query):
            return 1

    class FakeEngine:
        @contextmanager
        def connect(self):
            yield FakeConnection()

    monkeypatch.setattr(health, "engine", FakeEngine())
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "reachable"


def test_readiness_returns_503_when_database_is_unavailable(client, monkeypatch) -> None:
    class FakeEngine:
        @contextmanager
        def connect(self):
            raise OperationalError("connect", {}, RuntimeError("unavailable"))
            yield  # pragma: no cover - makes this a generator context manager

    monkeypatch.setattr(health, "engine", FakeEngine())
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["detail"] == "Database is unavailable"
