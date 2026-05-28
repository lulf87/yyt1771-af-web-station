from fastapi.testclient import TestClient
from yyt1771_af.main import app


def test_health_endpoint_returns_contract_payload() -> None:
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "app": "yyt1771-af-web-station",
        "version": "0.2.0",
    }
