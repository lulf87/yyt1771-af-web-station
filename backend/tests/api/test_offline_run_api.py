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


def _confirm_definition(client: TestClient, *, max_point_jump_px: float = 25.0) -> str:
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
                "max_point_jump_px": max_point_jump_px,
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


def test_offline_run_marks_excessive_point_jump_invalid(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    _write_frame(frames_dir / "frame_1.npy")
    _write_frame(frames_dir / "frame_2.npy", x_offset=20)
    client = TestClient(app)
    measurement_definition_id = _confirm_definition(client, max_point_jump_px=10.0)
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=measurement_definition_id,
    )
    session_id = opened["session_id"]

    first = client.post(f"/api/offline-run/{session_id}/next").json()
    second = client.post(f"/api/offline-run/{session_id}/next").json()

    assert first["detection"]["status"] == "ok"
    assert first["detection"]["valid"] is True
    assert second["detection"]["status"] == "jump_exceeds_limit"
    assert second["detection"]["valid"] is False
    assert second["detection"]["point_a"] is None
    assert second["detection"]["point_b"] is None
    assert second["detection"]["distance_px"] is None
    assert second["detection"]["diagnostics"]["rejected_candidate_point_a"] is not None
    assert second["detection"]["diagnostics"]["is_top_jump_candidate"] is True


def test_offline_run_seek_resets_previous_jump_baseline(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    _write_frame(frames_dir / "frame_1.npy")
    _write_frame(frames_dir / "frame_2.npy", x_offset=20)
    client = TestClient(app)
    measurement_definition_id = _confirm_definition(client, max_point_jump_px=10.0)
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=measurement_definition_id,
    )
    session_id = opened["session_id"]

    first = client.post(f"/api/offline-run/{session_id}/next").json()
    seek = client.post(f"/api/offline-run/{session_id}/seek", json={"frame_index": 1}).json()

    assert first["detection"]["status"] == "ok"
    assert seek["frame_index"] == 1
    assert seek["detection"]["status"] == "ok"
    assert seek["detection"]["valid"] is True
    assert seek["detection"]["point_a"] is not None
    assert seek["detection"]["diagnostics"].get("previous_measurement_line_y") is None


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
    assert diagnostics["point_a_source_interval"] is not None
    assert diagnostics["point_b_source_interval"] is not None
    assert diagnostics["selected_bundle_cluster_id"] is not None
    assert diagnostics["selected_bundle_support_ratio"] is not None
    assert diagnostics["selected_bundle_max_internal_gap_px"] is not None
    assert diagnostics["remote_interval_rejection_count"] == 0
    assert "selected_valid_intervals" not in diagnostics
    assert "rejected_remote_intervals" not in diagnostics

    inspected = client.post(f"/api/offline-run/{session_id}/inspect").json()
    inspected_diagnostics = inspected["detection"]["diagnostics"]
    assert (
        inspected_diagnostics["point_a_source_interval"]
        in inspected_diagnostics["selected_valid_intervals"]
    )
    assert (
        inspected_diagnostics["point_b_source_interval"]
        in inspected_diagnostics["selected_valid_intervals"]
    )
    assert (
        inspected_diagnostics["point_a_source_interval"]
        == inspected_diagnostics["leftmost_valid_interval"]
    )
    assert (
        inspected_diagnostics["point_b_source_interval"]
        == inspected_diagnostics["rightmost_valid_interval"]
    )
    assert "two_strip" not in json.dumps(diagnostics)


def test_setup_live_and_offline_validation_match_same_frame_and_recipe(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from yyt1771_af.core.models import RotatedRoi, SegmentationParams, WireStripDetectorParams
    from yyt1771_af.core.statuses import TargetFamily
    from yyt1771_af.services.offline_validation_service import (
        OfflineValidationRequest,
        run_offline_validation,
    )

    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    np.save(frames_dir / "frame_000001.npy", _wire_bundle_frame())
    monkeypatch.setenv("YYT1771_AF_OFFLINE_DIR", str(frames_dir))
    client = TestClient(app)
    client.post("/api/camera/open", json={"profile": "dev_offline"})
    frame_ref = client.post("/api/setup/freeze", json={"source": "latest"}).json()["frame_ref"]
    roi = {
        "center_x": 120.0,
        "center_y": 90.0,
        "width": 130.0,
        "height": 90.0,
        "angle_deg": 0.0,
        "coordinate_space": "acquisition",
    }
    segmentation = {
        "polarity": "dark_on_light",
        "threshold_mode": "fixed",
        "threshold_value": 140,
        "blur_kernel": 3,
        "close_kernel": 1,
        "open_kernel": 1,
        "min_component_area_px": 20,
        "fill_internal_holes": False,
    }
    detector = _complete_wire_detector_payload()
    setup_payload = {
        "frame_ref": frame_ref,
        "roi": roi,
        "target_family": "wire_strip",
        "recipe_name": "wire_strip_default",
        "segmentation": segmentation,
        "detector": detector,
    }
    setup_detection = client.post("/api/setup/detect", json=setup_payload).json()
    confirm_response = client.post(
        "/api/setup/confirm",
        json={
            "name": "same-frame-wire",
            "target_family": "wire_strip",
            "roi": roi,
            "recipe_name": "wire_strip_default",
            "segmentation": segmentation,
            "detector": detector,
        },
    )
    measurement_definition_id = confirm_response.json()["measurement_definition_id"]
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=measurement_definition_id,
    )
    session_id = opened["session_id"]
    live_basic = client.post(f"/api/offline-run/{session_id}/next").json()
    live_full = client.post(
        f"/api/offline-run/{session_id}/seek",
        json={"frame_index": 0},
    ).json()
    validation_dir = tmp_path / "validation"
    run_offline_validation(
        OfflineValidationRequest(
            frames_dir=frames_dir,
            target_family=TargetFamily.WIRE_STRIP,
            roi=RotatedRoi.model_validate(roi),
            fps=10.0,
            output_dir=validation_dir,
            max_frames=1,
            segmentation=SegmentationParams.model_validate(segmentation),
            detector=WireStripDetectorParams.model_validate(detector),
            recipe_name="wire_strip_default",
        )
    )
    validation_sample = json.loads(
        (validation_dir / "evaluation_samples.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )

    assert _formal_result(setup_detection) == _formal_result(live_basic["detection"])
    assert _formal_result(setup_detection) == _formal_result(live_full["detection"])
    assert _formal_result(setup_detection) == _formal_result(validation_sample)
    assert live_basic["runtime"]["debug_level"] == "basic"
    assert live_full["runtime"]["debug_level"] == "full"
    assert live_basic["detection"]["frame_identity"]["frame_name"] == "frame_000001.npy"
    assert live_full["detection"]["frame_identity"]["frame_name"] == "frame_000001.npy"
    assert validation_sample["frame_identity"]["frame_name"] == "frame_000001.npy"


def test_offline_run_probe_point_reports_rejected_remote_interval(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    np.save(frames_dir / "frame_000001.npy", _wire_bundle_with_remote_speck())
    client = TestClient(app)
    measurement_definition_id = _confirm_remote_speck_wire_definition(client)
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=measurement_definition_id,
    )
    session_id = opened["session_id"]
    seek = client.post(f"/api/offline-run/{session_id}/seek", json={"frame_index": 0}).json()
    assert seek["detection"]["diagnostics"]["remote_interval_rejection_count"] >= 1

    probe_response = client.post(
        f"/api/offline-run/{session_id}/probe-point",
        json={
            "frame_index": 0,
            "x": 265.0,
            "y": 110.0,
            "coordinate_space": "acquisition",
        },
    )

    assert probe_response.status_code == 200
    probe = probe_response.json()
    serialized = json.dumps(probe)
    assert str(frames_dir) not in serialized
    assert probe["frame_identity"]["frame_index"] == 0
    assert probe["frame_identity"]["frame_name"] == "frame_000001.npy"
    assert probe["raw_foreground"] is True
    assert probe["morphology_foreground"] is True
    assert probe["wire_foreground"] is True
    assert probe["component_accepted"] is True
    assert probe["rejected_remote_interval"] is True
    assert probe["reject_reason"] == "remote_gap_exceeded"
    assert probe["would_be_ab_source"] is False


def test_offline_run_roi_crop_uses_full_resolution_zoom(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    image = np.full((64, 80), 230, dtype=np.uint8)
    image[32, 44] = 30
    np.save(frames_dir / "frame_000001.npy", image)
    client = TestClient(app)
    measurement_definition_id = _confirm_small_crop_definition(client)
    opened = _open_live_run(
        client,
        frames_dir=frames_dir,
        measurement_definition_id=measurement_definition_id,
    )
    session_id = opened["session_id"]

    crop_response = client.get(f"/api/offline-run/{session_id}/frame/0/roi-crop.png?scale=4")

    assert crop_response.status_code == 200
    assert _png_size(crop_response.content) == (96, 72)


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
    for key in ("load_ms", "frame_load_ms", "detect_ms", "api_total_ms"):
        assert isinstance(runtime[key], (int, float))
        assert runtime[key] >= 0.0
    assert runtime["target_fps"] == 10.0
    assert runtime["frame_budget_ms"] == 100.0
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
    # heavy interval arrays while retaining formal source intervals for traceability.
    assert "raw_intervals" not in played["detection"]["diagnostics"]
    assert "selected_valid_intervals" not in played["detection"]["diagnostics"]
    assert "rejected_remote_intervals" not in played["detection"]["diagnostics"]
    assert seeked["detection"]["diagnostics"]["raw_intervals"] is not None


def test_offline_run_inspect_current_frame_returns_full_debug_without_advancing(
    tmp_path: Path,
) -> None:
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

    inspected = client.post(f"/api/offline-run/{session_id}/inspect").json()
    next_frame = client.post(f"/api/offline-run/{session_id}/next").json()

    assert inspected["frame_index"] == played["frame_index"]
    assert inspected["runtime"]["debug_level"] == "full"
    assert inspected["detection"]["diagnostics"]["raw_intervals"] is not None
    assert (
        inspected["detection"]["diagnostics"]["point_a_source_interval"]
        in inspected["detection"]["diagnostics"]["selected_valid_intervals"]
    )
    assert next_frame["frame_index"] == 1


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
    np.save(frames_dir / "frame_000001.npy", _wire_bundle_frame())
    _write_bad_color_frame(frames_dir / "frame_000002.npy")
    client = TestClient(app, raise_server_exceptions=False)
    measurement_definition_id = _confirm_wire_definition(client)
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
    assert traces[0]["point_a_source_interval"] is not None
    assert traces[0]["point_b_source_interval"] is not None
    assert traces[0]["selected_bundle_support_ratio"] is not None
    assert traces[0]["selected_bundle_max_internal_gap_px"] is not None
    assert traces[0]["selected_line_y"] is not None
    assert traces[0]["selected_line_span_px"] is not None
    assert traces[0]["selected_line_reason"] in {
        "max_formal_ab_span",
        "span_tie_break_support_ratio",
        "stable_bundle_plateau",
    }
    assert traces[0]["span_margin_to_second_best_px"] is not None
    assert traces[0]["top_candidate_lines"]
    assert traces[0]["top_candidate_lines"][0]["formal_ab_span_px"] is not None
    assert traces[0]["source_interval_ids"] is None
    assert traces[0]["point_a_source_interval_id"] is None
    assert traces[0]["point_b_source_interval_id"] is None
    assert "frame_load_ms" in traces[0]["timings_ms"]
    assert "detector_total_ms" in traces[0]["timings_ms"]
    assert traces[1]["valid"] is False
    assert traces[1]["error_code"] in {"frame_read_failed", "unsupported_frame_format"}
    assert traces[1]["frame_name"] == "frame_000002.npy"
    assert str(frames_dir) not in json.dumps(payload)


def _complete_wire_detector_payload() -> dict[str, object]:
    return {
        "detector_kind": "wire_strip_detector",
        "measurement_model": "blank_wire_bundle_envelope_blank",
        "measurement_mode": "wire_bundle_envelope",
        "min_quality": 0.65,
        "max_point_jump_px": 25.0,
        "reject_contact_on_roi_boundary": True,
        "boundary_margin_px": 3.0,
        "require_physical_endpoints": False,
        "skeleton_endpoint_detection": False,
        "preserve_visible_strip_contour": True,
        "min_interval_width_px": 3.0,
        "max_interval_width_ratio": 0.65,
        "min_valid_interval_count": 2,
        "min_local_contrast_score": 8.0,
        "min_wire_likeness_score": 0.0,
        "max_broad_blob_area_ratio": 0.22,
        "max_component_area_ratio": 0.45,
        "min_component_area_px": 40,
        "max_internal_gap_px": None,
        "max_internal_gap_ratio": 0.9,
        "max_bundle_internal_gap_px": 60.0,
        "max_bundle_internal_gap_ratio": 1.0,
        "min_neighbor_line_support": 1,
        "component_aspect_ratio_min": 1.8,
        "broad_blob_max_aspect_ratio": 1.8,
        "enable_broad_blob_rejection": True,
        "enable_local_contrast_filter": True,
        "enable_neighbor_line_support_filter": True,
        "enable_remote_interval_rejection": True,
        "enable_orientation_scoring": True,
    }


def _wire_bundle_with_remote_speck() -> np.ndarray:
    image = np.full((220, 320), 230, dtype=np.uint8)
    image[50:170, 64:72] = 30
    image[50:170, 98:108] = 30
    image[50:170, 134:148] = 30
    image[80:140, 262:268] = 30
    return image


def _confirm_remote_speck_wire_definition(client: TestClient) -> str:
    client.post("/api/camera/open", json={"profile": "dev_mock"})
    response = client.post(
        "/api/setup/confirm",
        json={
            "name": "remote-speck-wire",
            "target_family": "wire_strip",
            "roi": {
                "center_x": 160.0,
                "center_y": 110.0,
                "width": 280.0,
                "height": 150.0,
                "angle_deg": 0.0,
                "coordinate_space": "acquisition",
            },
            "recipe_name": "wire_strip_default",
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
            "detector": _complete_wire_detector_payload(),
        },
    )
    assert response.status_code == 200
    return str(response.json()["measurement_definition_id"])


def _confirm_small_crop_definition(client: TestClient) -> str:
    client.post("/api/camera/open", json={"profile": "dev_mock"})
    response = client.post(
        "/api/setup/confirm",
        json={
            "name": "small-crop",
            "target_family": "wire_strip",
            "roi": {
                "center_x": 40.0,
                "center_y": 32.0,
                "width": 24.0,
                "height": 18.0,
                "angle_deg": 0.0,
                "coordinate_space": "acquisition",
            },
            "recipe_name": "wire_strip_default",
            "segmentation": {
                "polarity": "dark_on_light",
                "threshold_mode": "fixed",
                "threshold_value": 100,
                "blur_kernel": 3,
                "close_kernel": 1,
                "open_kernel": 1,
                "min_component_area_px": 1,
                "fill_internal_holes": False,
            },
            "detector": _complete_wire_detector_payload(),
        },
    )
    assert response.status_code == 200
    return str(response.json()["measurement_definition_id"])


def _formal_result(payload: dict[str, object]) -> tuple[object, ...]:
    return (
        payload["status"],
        payload["valid"],
        _rounded_point(payload.get("point_a")),
        _rounded_point(payload.get("point_b")),
        round(float(payload["distance_px"]), 6) if payload.get("distance_px") is not None else None,
    )


def _rounded_point(value: object) -> tuple[float, float] | None:
    if not isinstance(value, dict):
        return None
    return (round(float(value["x"]), 6), round(float(value["y"]), 6))
