from pathlib import Path

from fastapi.testclient import TestClient
from yyt1771_af.main import app


def test_mock_camera_open_status_and_freeze_returns_acquisition_frame() -> None:
    client = TestClient(app)

    open_response = client.post("/api/camera/open", json={"profile": "dev_mock"})
    assert open_response.status_code == 200
    assert open_response.json() == {"opened": True, "source_type": "mock"}

    status_response = client.get("/api/camera/status")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["opened"] is True
    assert status_payload["source_type"] == "mock"
    assert status_payload["latest_frame_id"] >= 1
    assert status_payload["frame_width"] == 320
    assert status_payload["frame_height"] == 220
    assert status_payload["coordinate_space"] == "acquisition"

    freeze_response = client.post("/api/setup/freeze", json={"source": "latest"})
    assert freeze_response.status_code == 200
    freeze_payload = freeze_response.json()
    assert freeze_payload["preview_url"].startswith("/api/camera/frame/")
    assert "/preview.png" in freeze_payload["preview_url"]
    assert freeze_payload["frame_ref"] == {
        "frame_id": status_payload["latest_frame_id"],
        "timestamp_ms": freeze_payload["frame_ref"]["timestamp_ms"],
        "width": 320,
        "height": 220,
        "coordinate_space": "acquisition",
    }


def test_setup_detect_returns_backend_ab_points_for_balloon_recipe() -> None:
    client = TestClient(app)
    client.post("/api/camera/open", json={"profile": "dev_mock"})
    frame_ref = client.post("/api/setup/freeze", json={"source": "latest"}).json()["frame_ref"]

    detect_response = client.post(
        "/api/setup/detect",
        json={
            "frame_ref": frame_ref,
            "roi": {
                "center_x": 110.0,
                "center_y": 110.0,
                "width": 130.0,
                "height": 80.0,
                "angle_deg": 0.0,
                "coordinate_space": "acquisition",
            },
            "target_family": "balloon_envelope",
            "recipe_name": "balloon_envelope_default",
        },
    )

    assert detect_response.status_code == 200
    payload = detect_response.json()
    assert payload["status"] == "ok"
    assert payload["valid"] is True
    assert payload["target_family"] == "balloon_envelope"
    assert payload["detector"] == "balloon_envelope_detector:v1"
    assert payload["point_a"]["coordinate_space"] == "acquisition"
    assert payload["point_b"]["coordinate_space"] == "acquisition"
    assert payload["point_a"]["x"] < 70.0
    assert payload["point_b"]["x"] > 150.0
    assert payload["distance_px"] > 90.0
    assert 0.0 <= payload["quality"] <= 1.0
    assert "diagnostics" in payload


def test_setup_detect_returns_backend_ab_points_for_wire_recipe() -> None:
    client = TestClient(app)
    client.post("/api/camera/open", json={"profile": "dev_mock"})
    frame_ref = client.post("/api/setup/freeze", json={"source": "latest"}).json()["frame_ref"]

    detect_response = client.post(
        "/api/setup/detect",
        json={
            "frame_ref": frame_ref,
            "roi": {
                "center_x": 235.0,
                "center_y": 110.0,
                "width": 55.0,
                "height": 150.0,
                "angle_deg": 90.0,
                "coordinate_space": "acquisition",
            },
            "target_family": "wire_strip",
            "recipe_name": "wire_strip_default",
        },
    )

    assert detect_response.status_code == 200
    payload = detect_response.json()
    assert payload["status"] == "ok"
    assert payload["valid"] is True
    assert payload["target_family"] == "wire_strip"
    assert payload["detector"] == "wire_strip_detector:v1"
    assert payload["point_a"]["coordinate_space"] == "acquisition"
    assert payload["point_b"]["coordinate_space"] == "acquisition"
    assert 15.0 <= payload["distance_px"] <= 24.0


def test_offline_camera_open_reads_pgm_image_folder(
    monkeypatch,
    tmp_path: Path,
) -> None:
    frame_path = tmp_path / "frame_001.pgm"
    frame_path.write_bytes(
        b"P2\n"
        b"6 4\n"
        b"255\n"
        b"230 230 230 230 230 230\n"
        b"230 30 30 30 30 230\n"
        b"230 30 30 30 30 230\n"
        b"230 230 230 230 230 230\n"
    )
    monkeypatch.setenv("YYT1771_AF_OFFLINE_DIR", str(tmp_path))
    client = TestClient(app)

    open_response = client.post("/api/camera/open", json={"profile": "dev_offline"})
    assert open_response.status_code == 200
    assert open_response.json() == {"opened": True, "source_type": "offline"}

    status_payload = client.get("/api/camera/status").json()
    assert status_payload["opened"] is True
    assert status_payload["source_type"] == "offline"
    assert status_payload["frame_width"] == 6
    assert status_payload["frame_height"] == 4
    assert status_payload["coordinate_space"] == "acquisition"
