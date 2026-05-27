from fastapi.testclient import TestClient
from yyt1771_af.main import app


def test_temperature_status_reports_disconnected_controller(monkeypatch) -> None:
    monkeypatch.setenv("YYT1771_AF_TEMPERATURE_SOURCE", "mock")
    monkeypatch.setenv("YYT1771_AF_TEMPERATURE_CONNECTED", "0")
    client = TestClient(app)

    response = client.get("/api/temperature/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["controller_type"] == "mock"
    assert payload["connected"] is False
    assert payload["status"] == "disconnected"


def test_temperature_current_reports_not_connected(monkeypatch) -> None:
    monkeypatch.setenv("YYT1771_AF_TEMPERATURE_SOURCE", "mock")
    monkeypatch.setenv("YYT1771_AF_TEMPERATURE_CONNECTED", "0")
    client = TestClient(app)

    response = client.get("/api/temperature/current")

    assert response.status_code == 200
    payload = response.json()
    assert payload["temperature_c"] is None
    assert payload["status"] == "not_connected"
    assert payload["source_type"] == "mock"


def test_temperature_api_accepts_target_power_and_output(monkeypatch) -> None:
    monkeypatch.setenv("YYT1771_AF_TEMPERATURE_SOURCE", "mock")
    monkeypatch.setenv("YYT1771_AF_TEMPERATURE_CONNECTED", "1")
    client = TestClient(app)

    target_response = client.post("/api/temperature/target", json={"target_c": 48.0})
    power_response = client.post("/api/temperature/power", json={"power_percent": 35.0})
    output_response = client.post("/api/temperature/output", json={"enabled": True})

    assert target_response.status_code == 200
    assert target_response.json()["status"] == "ok"
    assert target_response.json()["snapshot"]["target_temperature_c"] == 48.0
    assert power_response.status_code == 200
    assert power_response.json()["status"] == "ok"
    assert power_response.json()["snapshot"]["power_percent"] == 35.0
    assert output_response.status_code == 200
    assert output_response.json()["status"] == "ok"
    assert output_response.json()["snapshot"]["output_enabled"] is True


def test_temperature_api_rejects_invalid_power_percent(monkeypatch) -> None:
    monkeypatch.setenv("YYT1771_AF_TEMPERATURE_SOURCE", "mock")
    monkeypatch.setenv("YYT1771_AF_TEMPERATURE_CONNECTED", "1")
    client = TestClient(app)

    response = client.post("/api/temperature/power", json={"power_percent": 125.0})

    assert response.status_code == 422
