from fastapi.testclient import TestClient

from app.main import app


def test_api_routes_exist():
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/devices").status_code == 200
        assert client.get("/jobs").status_code == 200
        assert client.get("/metrics/summary").status_code == 200
