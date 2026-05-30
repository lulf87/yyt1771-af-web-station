from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from yyt1771_af.main import app


def _write_frame(path: Path, *, x_offset: int = 0, value: int = 30) -> None:
    image = np.full((220, 320), 230, dtype=np.uint8)
    image[78:142, 58 + x_offset : 164 + x_offset] = value
    np.save(path, image)


def _write_bad_color_frame(path: Path) -> None:
    image = np.full((220, 320, 3), 230, dtype=np.uint8)
    np.save(path, image)


def _png_size(payload: bytes) -> tuple[int, int]:
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    return struct.unpack(">II", payload[16:24])


def _confirm_definition(client: TestClient) -> str:
    client.post("/api/camera/open", json={"profile": "dev_mock"})
    response = client.post(
        "/api/setup/confirm",
        json={
            "name": "live-offline",
            "target_family": "balloon_envelope",
            "roi": {
                "center_x": 110.0,
                "center_y": 110.0,
                "width": 160.0,
                "height": 100.0,
                "angle_deg": 0.0,
                "coordinate_space": "acquisition",
            },
            "recipe_name": "balloon_envelope_default",
            "segmentation": {
                "polarity": "dark_on_light",
                "threshold_mode": "fixed",
                "threshold_value": 160,
                "blur_kernel": 3,
                "close_kernel": 1,
                "open_kernel": 1,
                "min_component_area_px": 20,
                "fill_internal_holes": False,
            },
            "detector": {
                "detector_kind": "balloon_envelope_detector",
                "envelope_mode": "solid_balloon",
                "contact_source": "filled_envelope",
                "measurement_model": "blank_object_blank",
                "min_quality": 0.65,
                "max_point_jump_px": 25.0,
                "reject_contact_on_roi_boundary": True,
                "boundary_margin_px": 4.0,
                "ignore_internal_texture": True,
                "fill_internal_holes": True,
                "bridge_mesh_gaps": True,
            },
        },
    )
    assert response.status_code == 200
    return str(response.json()["measurement_definition_id"])


def _open_live_run(
    client: TestClient,
    *,
    frames_dir: Path | None,
    measurement_definition_id: str,
    loop: bool = True,
) -> dict[str, object]:
    payload = {
        "measurement_definition_id": measurement_definition_id,
        "frames_dir": str(frames_dir) if frames_dir is not None else None,
        "fps": 10.0,
        "loop": loop,
        "dataset_label": None,
        "start_frame_index": 0,
        "max_preview_width": 160,
    }
    response = client.post("/api/offline-run/open", json=payload)
    assert response.status_code == 200
    return response.json()


def test_offline_run_open_uses_env_and_does_not_leak_absolute_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    frames_dir = tmp_path / "private_frames"
    frames_dir.mkdir()
    _write_frame(frames_dir / "frame_000001.npy")
    _write_frame(frames_dir / "frame_000002.npy", x_offset=4)
    monkeypatch.setenv("YYT1771_AF_OFFLINE_DIR", str(frames_dir))
    client = TestClient(app)
    measurement_definition_id = _confirm_definition(client)

    payload = _open_live_run(
        client,
        frames_dir=None,
        measurement_definition_id=measurement_definition_id,
    )

    serialized = json.dumps(payload)
    assert str(frames_dir) not in serialized
    assert payload["opened"] is True
    assert str(payload["session_id"]).startswith("offline_run_")
    assert payload["frame_count"] == 2
    assert payload["dataset_label"] == "private_frames"
    assert payload["measurement_definition_id"] == measurement_definition_id


def test_offline_run_next_seek_previous_loop_and_preview_are_session_scoped(
    tmp_path: Path,
) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    _write_frame(frames_dir / "frame_1.npy")
    _write_frame(frames_dir / "frame_2.npy", x_offset=5)
    client = TestClient(app)
    measurement_definition_id = _confirm_definition(client)
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=measurement_definition_id,
    )
    session_id = opened["session_id"]

    first = client.post(f"/api/offline-run/{session_id}/next").json()
    second = client.post(f"/api/offline-run/{session_id}/next").json()
    looped = client.post(f"/api/offline-run/{session_id}/next").json()
    previous = client.post(f"/api/offline-run/{session_id}/previous").json()
    seek = client.post(f"/api/offline-run/{session_id}/seek", json={"frame_index": 1}).json()
    preview = client.get(f"/api/offline-run/{session_id}/frame/1/preview.png?max_width=160")

    assert first["frame_index"] == 0
    assert first["frame_name"] == "frame_1.npy"
    assert first["preview_url"].startswith(f"/api/offline-run/{session_id}/frame/0/")
    assert first["detection"]["point_a"]["coordinate_space"] == "acquisition"
    assert first["detection"]["diagnostics"]["measurement_line_y"] is not None
    assert first["runtime"]["run_mode"] == "live_offline"
    assert first["runtime"]["recipe_locked"] is True
    assert second["frame_index"] == 1
    assert looped["frame_index"] == 0
    assert previous["frame_index"] == 1
    assert seek["frame_index"] == 1
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert _png_size(preview.content) == (160, 110)


def test_offline_run_loop_false_returns_end_of_stream(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    _write_frame(frames_dir / "frame_000001.npy")
    client = TestClient(app)
    measurement_definition_id = _confirm_definition(client)
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=measurement_definition_id,
        loop=False,
    )
    session_id = opened["session_id"]

    first = client.post(f"/api/offline-run/{session_id}/next").json()
    ended = client.post(f"/api/offline-run/{session_id}/next").json()

    assert first["frame_index"] == 0
    assert first["end_of_stream"] is False
    assert ended["frame_index"] == 0
    assert ended["end_of_stream"] is True


def _confirm_wire_definition(client: TestClient) -> str:
    client.post("/api/camera/open", json={"profile": "dev_mock"})
    response = client.post(
        "/api/setup/confirm",
        json={
            "name": "live-offline-wire",
            "target_family": "wire_strip",
            "roi": {
                "center_x": 120.0,
                "center_y": 90.0,
                "width": 130.0,
                "height": 90.0,
                "angle_deg": 0.0,
                "coordinate_space": "acquisition",
            },
            "recipe_name": "wire_strip_default",
            "segmentation": {
                "polarity": "dark_on_light",
                "threshold_mode": "fixed",
                "threshold_value": 140,
                "blur_kernel": 3,
                "close_kernel": 1,
                "open_kernel": 1,
                "min_component_area_px": 20,
                "fill_internal_holes": False,
            },
            "detector": {
                "detector_kind": "wire_strip_detector",
                "measurement_mode": "wire_bundle_envelope",
                "min_quality": 0.65,
                "max_point_jump_px": 25.0,
                "reject_contact_on_roi_boundary": True,
                "boundary_margin_px": 3.0,
            },
        },
    )
    assert response.status_code == 200
    return str(response.json()["measurement_definition_id"])


def _wire_bundle_frame() -> np.ndarray:
    image = np.full((220, 320), 230, dtype=np.uint8)
    image[78:142, 50:70] = 30
    image[78:142, 100:110] = 30
    image[78:142, 150:170] = 30
    return image


def test_offline_run_wire_strip_uses_wire_bundle_envelope(tmp_path: Path) -> None:
    frames_dir = tmp_path / "wire_frames"
    frames_dir.mkdir()
    np.save(frames_dir / "frame_000001.npy", _wire_bundle_frame())
    client = TestClient(app)
    measurement_definition_id = _confirm_wire_definition(client)
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=measurement_definition_id,
    )
    session_id = opened["session_id"]
    frame = client.post(f"/api/offline-run/{session_id}/next").json()
    diagnostics = frame["detection"]["diagnostics"]
    assert diagnostics["measurement_mode"] == "wire_bundle_envelope"
    assert "two_strip" not in json.dumps(diagnostics)


def test_offline_run_invalid_frame_returns_null_formal_points(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    _write_frame(frames_dir / "frame_000001.npy")
    client = TestClient(app)
    client.post("/api/camera/open", json={"profile": "dev_mock"})
    confirm = client.post(
        "/api/setup/confirm",
        json={
            "name": "invalid-live",
            "target_family": "wire_strip",
            "roi": {
                "center_x": 110.0,
                "center_y": 110.0,
                "width": 8.0,
                "height": 150.0,
                "angle_deg": 90.0,
                "coordinate_space": "acquisition",
            },
            "recipe_name": "wire_strip_default",
        },
    )
    measurement_definition_id = confirm.json()["measurement_definition_id"]
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=measurement_definition_id,
    )
    session_id = opened["session_id"]
    frame = client.post(f"/api/offline-run/{session_id}/next").json()
    detection = frame["detection"]
    assert detection["valid"] is False
    assert detection["point_a"] is None
    assert detection["point_b"] is None
    assert detection["distance_px"] is None


def test_offline_run_records_distance_jump_between_valid_frames(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    _write_frame(frames_dir / "frame_000001.npy", x_offset=0)
    _write_frame(frames_dir / "frame_000002.npy", x_offset=8)
    client = TestClient(app)
    measurement_definition_id = _confirm_definition(client)
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=measurement_definition_id,
    )
    session_id = opened["session_id"]
    first = client.post(f"/api/offline-run/{session_id}/next").json()
    second = client.post(f"/api/offline-run/{session_id}/next").json()
    if first["detection"]["valid"] and second["detection"]["valid"]:
        assert second["detection"]["diagnostics"].get("distance_jump_from_previous") is not None


def test_offline_run_sessions_are_isolated(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    _write_frame(dir_a / "frame_000001.npy")
    _write_frame(dir_b / "frame_000001.npy", x_offset=20)
    client = TestClient(app)
    measurement_definition_id = _confirm_definition(client)
    opened_a = _open_live_run(
        client,
        frames_dir=dir_a,
        measurement_definition_id=measurement_definition_id,
    )
    opened_b = _open_live_run(
        client,
        frames_dir=dir_b,
        measurement_definition_id=measurement_definition_id,
    )
    assert opened_a["session_id"] != opened_b["session_id"]
    frame_a = client.post(f"/api/offline-run/{opened_a['session_id']}/next").json()
    frame_b = client.post(f"/api/offline-run/{opened_b['session_id']}/next").json()
    assert opened_a["session_id"] in frame_a["preview_url"]
    assert opened_b["session_id"] in frame_b["preview_url"]
    assert frame_a["preview_url"] != frame_b["preview_url"]


def test_offline_run_uses_capture_temperature_csv_when_present(tmp_path: Path) -> None:
    capture_dir = tmp_path / "capture"
    frames_dir = capture_dir / "frames"
    frames_dir.mkdir(parents=True)
    (capture_dir / "temperature.csv").write_text(
        "\n".join(
            [
                "frame_index,camera_timestamp_ms,temp_timestamp_ms,celsius,source,sampled_this_frame,error",
                "1,1000,1001,20.5,lu92xx_modbus_rtu,1,",
                "2,1100,1001,22.0,lu92xx_modbus_rtu,1,",
            ]
        ),
        encoding="utf-8",
    )
    _write_frame(frames_dir / "frame_000001.npy")
    _write_frame(frames_dir / "frame_000002.npy", x_offset=4)
    client = TestClient(app)
    measurement_definition_id = _confirm_definition(client)
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=measurement_definition_id,
    )
    assert opened["temperature_trace_available"] is True
    assert opened["temperature_source_type"] == "capture_csv"

    session_id = opened["session_id"]
    first = client.post(f"/api/offline-run/{session_id}/next").json()
    second = client.post(f"/api/offline-run/{session_id}/next").json()

    assert first["runtime"]["temperature_c"] == 20.5
    assert first["runtime"]["temperature_source_type"] == "capture_csv"
    assert first["runtime"]["temperature_source"] == "lu92xx_modbus_rtu"
    assert second["runtime"]["temperature_c"] == 22.0
    assert str(capture_dir) not in json.dumps(first)


def test_offline_run_next_includes_material_time_and_mock_temperature(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    _write_frame(frames_dir / "frame_000001.npy")
    _write_frame(frames_dir / "frame_000002.npy", x_offset=4)
    client = TestClient(app)
    measurement_definition_id = _confirm_definition(client)
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=measurement_definition_id,
    )
    session_id = opened["session_id"]

    first = client.post(f"/api/offline-run/{session_id}/next").json()
    second = client.post(f"/api/offline-run/{session_id}/next").json()

    assert first["relative_time_s"] == 0.0
    assert second["relative_time_s"] == 0.1
    assert first["runtime"]["total_duration_s"] == 0.1
    assert first["runtime"]["temperature_c"] == 0.0
    assert second["runtime"]["temperature_c"] == 0.1
    assert first["runtime"]["temperature_status"] == "ok"


def test_offline_run_next_reports_timing_and_uses_basic_debug_level(tmp_path: Path) -> None:
    frames_dir = tmp_path / "wire_frames"
    frames_dir.mkdir()
    np.save(frames_dir / "frame_000001.npy", _wire_bundle_frame())
    np.save(frames_dir / "frame_000002.npy", _wire_bundle_frame())
    client = TestClient(app)
    measurement_definition_id = _confirm_wire_definition(client)
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=measurement_definition_id,
    )
    session_id = opened["session_id"]

    played = client.post(f"/api/offline-run/{session_id}/next").json()
    seeked = client.post(f"/api/offline-run/{session_id}/seek", json={"frame_index": 0}).json()

    runtime = played["runtime"]
    for key in ("load_ms", "detect_ms", "api_total_ms"):
        assert isinstance(runtime[key], (int, float))
        assert runtime[key] >= 0.0
    assert "preview_encode_ms" in runtime
    for key in (
        "segmentation_ms",
        "connected_components_ms",
        "wire_filtering_ms",
        "line_scan_ms",
        "candidate_scoring_ms",
        "diagnostics_ms",
        "detector_total_ms",
    ):
        assert isinstance(runtime[key], (int, float))
        assert runtime[key] >= 0.0

    # Playback uses the lightweight basic level; seek/single-frame uses full.
    assert played["runtime"]["debug_level"] == "basic"
    assert seeked["runtime"]["debug_level"] == "full"

    # Both produce the same valid formal A/B; only diagnostic depth differs.
    assert played["detection"]["valid"] is True
    assert seeked["detection"]["valid"] is True
    assert played["detection"]["distance_px"] == seeked["detection"]["distance_px"]
    # Serialized diagnostics drop None fields, so the basic playback frame omits
    # the heavy raw intervals while the full seek frame includes them.
    assert "raw_intervals" not in played["detection"]["diagnostics"]
    assert seeked["detection"]["diagnostics"]["raw_intervals"] is not None


def test_offline_run_close_makes_session_unavailable(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    _write_frame(frames_dir / "frame_000001.npy")
    client = TestClient(app)
    measurement_definition_id = _confirm_definition(client)
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=measurement_definition_id,
    )
    session_id = opened["session_id"]

    close = client.post(f"/api/offline-run/{session_id}/close")
    next_response = client.post(f"/api/offline-run/{session_id}/next")

    assert close.status_code == 200
    assert close.json() == {"session_id": session_id, "closed": True}
    assert next_response.status_code == 404
    payload = next_response.json()
    assert payload["error_code"] == "session_not_found"
    assert payload["state"] == "error"
    assert payload["session_id"] == session_id


def test_offline_run_next_exception_returns_sanitized_json_error(tmp_path: Path) -> None:
    frames_dir = tmp_path / "private_frames"
    frames_dir.mkdir()
    _write_bad_color_frame(frames_dir / "frame_000001.npy")
    client = TestClient(app, raise_server_exceptions=False)
    measurement_definition_id = _confirm_definition(client)
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=measurement_definition_id,
    )
    session_id = opened["session_id"]

    response = client.post(f"/api/offline-run/{session_id}/next")

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] in {"frame_read_failed", "unsupported_frame_format"}
    assert payload["state"] == "error"
    assert payload["frame_index"] == 0
    assert payload["frame_name"] == "frame_000001.npy"
    assert payload["session_id"] == session_id
    assert str(frames_dir) not in json.dumps(payload)
    assert "/Users/" not in json.dumps(payload)


def test_offline_run_preview_exception_returns_sanitized_json_error(tmp_path: Path) -> None:
    frames_dir = tmp_path / "private_frames"
    frames_dir.mkdir()
    _write_bad_color_frame(frames_dir / "frame_000001.npy")
    client = TestClient(app, raise_server_exceptions=False)
    measurement_definition_id = _confirm_definition(client)
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=measurement_definition_id,
    )
    session_id = opened["session_id"]

    response = client.get(f"/api/offline-run/{session_id}/frame/0/preview.png?max_width=160")

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] in {
        "frame_read_failed",
        "preview_encode_failed",
        "unsupported_frame_format",
    }
    assert payload["state"] == "error"
    assert payload["frame_index"] == 0
    assert payload["frame_name"] == "frame_000001.npy"
    assert str(frames_dir) not in json.dumps(payload)


def test_offline_run_invalid_detection_is_not_api_error(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    _write_frame(frames_dir / "frame_000001.npy")
    client = TestClient(app, raise_server_exceptions=False)
    client.post("/api/camera/open", json={"profile": "dev_mock"})
    confirm = client.post(
        "/api/setup/confirm",
        json={
            "name": "invalid-live",
            "target_family": "wire_strip",
            "roi": {
                "center_x": 110.0,
                "center_y": 110.0,
                "width": 8.0,
                "height": 150.0,
                "angle_deg": 90.0,
                "coordinate_space": "acquisition",
            },
            "recipe_name": "wire_strip_default",
        },
    )
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=confirm.json()["measurement_definition_id"],
    )
    session_id = opened["session_id"]

    response = client.post(f"/api/offline-run/{session_id}/next")

    assert response.status_code == 200
    payload = response.json()
    assert "error_code" not in payload
    assert payload["detection"]["valid"] is False
    assert payload["detection"]["distance_px"] is None


def test_offline_run_trace_records_success_and_error_frames(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    _write_frame(frames_dir / "frame_000001.npy")
    _write_bad_color_frame(frames_dir / "frame_000002.npy")
    client = TestClient(app, raise_server_exceptions=False)
    measurement_definition_id = _confirm_definition(client)
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=measurement_definition_id,
    )
    session_id = opened["session_id"]

    ok_response = client.post(f"/api/offline-run/{session_id}/next")
    error_response = client.post(f"/api/offline-run/{session_id}/next")
    trace_response = client.get(f"/api/offline-run/{session_id}/trace")

    assert ok_response.status_code == 200
    assert error_response.status_code == 400
    assert trace_response.status_code == 200
    payload = trace_response.json()
    assert payload["session_id"] == session_id
    traces = payload["traces"]
    assert [item["frame_index"] for item in traces] == [0, 1]
    assert traces[0]["valid"] is True
    assert traces[0]["error_code"] is None
    assert traces[1]["valid"] is False
    assert traces[1]["error_code"] in {"frame_read_failed", "unsupported_frame_format"}
    assert traces[1]["frame_name"] == "frame_000002.npy"
    assert str(frames_dir) not in json.dumps(payload)
