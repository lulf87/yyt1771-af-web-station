import json
import struct
import zlib
from pathlib import Path

import numpy as np
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
    assert freeze_payload["frame_identity"] == {
        "frame_id": status_payload["latest_frame_id"],
        "frame_index": status_payload["latest_frame_id"] - 1,
        "frame_name": f"mock_{status_payload['latest_frame_id']:06d}",
        "source_type": "mock",
        "acquisition_width": 320,
        "acquisition_height": 220,
        "recipe_summary": None,
        "debug_level": None,
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
    assert payload["debug_overlay_url"].startswith("/api/setup/debug-overlay/")
    assert payload["frame_identity"]["frame_id"] == frame_ref["frame_id"]
    assert payload["frame_identity"]["source_type"] == "mock"
    assert payload["frame_identity"]["recipe_summary"]["recipe_name"] == "balloon_envelope_default"
    assert payload["frame_identity"]["debug_level"] == "full"


def test_setup_detect_accepts_segmentation_override_and_serves_debug_overlay() -> None:
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
            "segmentation": {
                "polarity": "dark_on_light",
                "threshold_mode": "otsu",
                "threshold_value": None,
                "blur_kernel": 3,
                "close_kernel": 7,
                "open_kernel": 1,
                "min_component_area_px": 50,
            },
        },
    )

    assert detect_response.status_code == 200
    payload = detect_response.json()
    assert payload["diagnostics"]["selected_polarity"] == "dark_on_light"
    assert payload["diagnostics"]["selected_reason"] == "forced_dark"
    assert payload["diagnostics"]["threshold_value"] is not None
    assert "raw_foreground_ratio" in payload["diagnostics"]
    assert "morphology_foreground_ratio" in payload["diagnostics"]
    assert "filled_envelope_ratio" in payload["diagnostics"]
    assert "fill_internal_holes_used" in payload["diagnostics"]
    assert payload["diagnostics"]["contact_source_used"] == "filled_envelope"
    assert payload["debug_overlay_url"].startswith("/api/setup/debug-overlay/")

    overlay_response = client.get(
        payload["debug_overlay_url"]
        + "&show_raw_foreground=false"
        + "&show_morphology_foreground=true"
        + "&show_filled_envelope=true"
        + "&show_selected_contour=true"
        + "&show_rejected_candidates=true"
    )
    assert overlay_response.status_code == 200
    assert overlay_response.headers["content-type"] == "image/png"
    assert overlay_response.content.startswith(b"\x89PNG")


def test_setup_point_probe_explains_rejected_remote_speck(
    monkeypatch,
    tmp_path: Path,
) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    frame = _wire_bundle_with_remote_speck()
    np.save(frames_dir / "frame_000001.npy", frame)
    monkeypatch.setenv("YYT1771_AF_OFFLINE_DIR", str(frames_dir))
    client = TestClient(app)
    client.post("/api/camera/open", json={"profile": "dev_offline"})
    freeze_payload = client.post("/api/setup/freeze", json={"source": "latest"}).json()
    frame_ref = freeze_payload["frame_ref"]
    recipe = _wire_remote_speck_recipe(frame_ref)

    detect_response = client.post("/api/setup/detect", json=recipe)
    assert detect_response.status_code == 200
    detection = detect_response.json()
    assert detection["valid"] is True
    assert detection["frame_identity"]["frame_name"] == "frame_000001.npy"
    assert detection["diagnostics"]["remote_interval_rejection_count"] >= 1

    probe_response = client.post(
        "/api/setup/probe-point",
        json=recipe
        | {
            "x": 265.0,
            "y": 110.0,
            "coordinate_space": "acquisition",
        },
    )

    assert probe_response.status_code == 200
    probe = probe_response.json()
    serialized = json.dumps(probe)
    assert str(frames_dir) not in serialized
    assert probe["frame_identity"]["frame_name"] == "frame_000001.npy"
    assert probe["pixel_value"] == 30
    assert probe["inside_roi"] is True
    assert probe["raw_foreground"] is True
    assert probe["morphology_foreground"] is True
    assert probe["wire_foreground"] is True
    assert probe["component_id"] is not None
    assert probe["component_accepted"] is True
    assert probe["component_reject_reason"] is None
    assert probe["selected_valid_interval"] is False
    assert probe["rejected_remote_interval"] is True
    assert probe["reject_reason"] == "remote_gap_exceeded"
    assert probe["would_be_ab_source"] is False


def test_setup_point_probe_returns_false_null_for_background(
    monkeypatch,
    tmp_path: Path,
) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    np.save(frames_dir / "frame_000001.npy", _wire_bundle_with_remote_speck())
    monkeypatch.setenv("YYT1771_AF_OFFLINE_DIR", str(frames_dir))
    client = TestClient(app)
    client.post("/api/camera/open", json={"profile": "dev_offline"})
    frame_ref = client.post("/api/setup/freeze", json={"source": "latest"}).json()["frame_ref"]
    recipe = _wire_remote_speck_recipe(frame_ref)

    probe_response = client.post(
        "/api/setup/probe-point",
        json=recipe
        | {
            "x": 10.0,
            "y": 10.0,
            "coordinate_space": "acquisition",
        },
    )

    assert probe_response.status_code == 200
    probe = probe_response.json()
    assert probe["pixel_value"] == 230
    assert probe["inside_roi"] is False
    assert probe["raw_foreground"] is False
    assert probe["morphology_foreground"] is False
    assert probe["wire_foreground"] is False
    assert probe["component_id"] is None
    assert probe["component_accepted"] is None
    assert probe["component_reject_reason"] is None
    assert probe["interval_id"] is None
    assert probe["selected_valid_interval"] is False
    assert probe["rejected_interval"] is False
    assert probe["rejected_remote_interval"] is False
    assert probe["would_be_ab_source"] is False


def test_setup_roi_crop_zoom_preserves_one_pixel_speck(
    monkeypatch,
    tmp_path: Path,
) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    frame = np.full((64, 80), 230, dtype=np.uint8)
    frame[32, 44] = 30
    np.save(frames_dir / "frame_000001.npy", frame)
    monkeypatch.setenv("YYT1771_AF_OFFLINE_DIR", str(frames_dir))
    client = TestClient(app)
    client.post("/api/camera/open", json={"profile": "dev_offline"})
    frame_ref = client.post("/api/setup/freeze", json={"source": "latest"}).json()["frame_ref"]
    detect_response = client.post(
        "/api/setup/detect",
        json={
            "frame_ref": frame_ref,
            "roi": {
                "center_x": 40.0,
                "center_y": 32.0,
                "width": 24.0,
                "height": 18.0,
                "angle_deg": 0.0,
                "coordinate_space": "acquisition",
            },
            "target_family": "wire_strip",
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
        },
    )
    assert detect_response.status_code == 200
    crop_url = detect_response.json()["roi_crop_url"]

    crop_response = client.get(crop_url + "&scale=4")

    assert crop_response.status_code == 200
    width, height, pixels = _decode_rgb_png(crop_response.content)
    assert (width, height) == (96, 72)
    dark_pixels = int(np.count_nonzero(np.all(pixels < 80, axis=2)))
    assert dark_pixels == 16


def test_setup_detect_and_confirm_accept_complete_open_mesh_recipe_snapshot() -> None:
    client = TestClient(app)
    client.post("/api/camera/open", json={"profile": "dev_mock"})
    frame_ref = client.post("/api/setup/freeze", json={"source": "latest"}).json()["frame_ref"]
    recipe_payload = {
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
        "recipe_name": "open_mesh_setup",
        "segmentation": {
            "polarity": "dark_on_light",
            "threshold_mode": "fixed",
            "threshold_value": 160,
            "blur_kernel": 3,
            "close_kernel": 7,
            "open_kernel": 1,
            "min_component_area_px": 50,
            "fill_internal_holes": False,
        },
        "detector": {
            "detector_kind": "balloon_envelope_detector",
            "envelope_mode": "open_mesh",
            "contact_source": "bridged_foreground",
            "min_quality": 0.65,
            "reject_contact_on_roi_boundary": True,
            "boundary_margin_px": 4.0,
            "max_point_jump_px": 25.0,
            "ignore_internal_texture": True,
            "fill_internal_holes": False,
            "bridge_mesh_gaps": True,
        },
    }

    detect_response = client.post("/api/setup/detect", json=recipe_payload)
    assert detect_response.status_code == 200
    diagnostics = detect_response.json()["diagnostics"]
    assert diagnostics["envelope_mode"] == "open_mesh"
    assert diagnostics["configured_contact_source"] == "bridged_foreground"
    assert diagnostics["contact_source_used"] == "bridged_foreground"
    assert (
        diagnostics["actual_contact_source_area_ratio"] == diagnostics["bridged_foreground_ratio"]
    )

    confirm_payload = recipe_payload.copy()
    confirm_payload.pop("frame_ref")
    confirm_payload["name"] = "open-mesh-run"
    confirm_response = client.post("/api/setup/confirm", json=confirm_payload)

    assert confirm_response.status_code == 200
    measurement_definition = confirm_response.json()["measurement_definition"]
    assert measurement_definition["segmentation"]["threshold_mode"] == "fixed"
    assert measurement_definition["segmentation"]["threshold_value"] == 160
    assert measurement_definition["detector"]["envelope_mode"] == "open_mesh"
    assert measurement_definition["detector"]["contact_source"] == "bridged_foreground"
    assert measurement_definition["detector"]["boundary_margin_px"] == 4.0


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
    assert 40.0 <= payload["distance_px"] <= 50.0
    assert payload["diagnostics"]["measurement_mode"] == "wire_bundle_envelope"
    assert payload["diagnostics"]["detected_pattern"] == "wire_bundle_envelope"
    assert payload["diagnostics"]["object_interval_count"] >= 2
    assert payload["diagnostics"]["interval_count"] >= 2


def test_setup_wire_auto_tune_recommends_threshold_and_confirm_marks_auto_tuned() -> None:
    client = TestClient(app)
    client.post("/api/camera/open", json={"profile": "dev_mock"})
    frame_ref = client.post("/api/setup/freeze", json={"source": "latest"}).json()["frame_ref"]
    roi = {
        "center_x": 235.0,
        "center_y": 110.0,
        "width": 55.0,
        "height": 150.0,
        "angle_deg": 90.0,
        "coordinate_space": "acquisition",
    }

    auto_tune_response = client.post(
        "/api/setup/wire-auto-tune",
        json={
            "frame_ref": frame_ref,
            "roi": roi,
            "recipe_name": "wire_strip_default",
        },
    )

    assert auto_tune_response.status_code == 200
    payload = auto_tune_response.json()
    assert payload["target_family"] == "wire_strip"
    assert payload["auto_tuned"] is True
    assert payload["recommended_threshold_value"] is not None
    assert payload["recommended_segmentation"]["threshold_mode"] == "fixed"
    assert (
        payload["recommended_segmentation"]["threshold_value"]
        == (payload["recommended_threshold_value"])
    )
    assert len(payload["candidates"]) >= 1
    candidate = payload["candidates"][0]
    assert "score" in candidate
    assert "on_stable_platform" in candidate
    # No absolute paths leak through diagnostics-style payloads.
    assert "/" not in str(payload["selected_reason"])

    confirm_response = client.post(
        "/api/setup/confirm",
        json={
            "name": "wire-auto-tuned",
            "target_family": "wire_strip",
            "roi": roi,
            "recipe_name": "wire_strip_default",
            "segmentation": payload["recommended_segmentation"],
            "auto_tuned": True,
        },
    )
    assert confirm_response.status_code == 200
    measurement_definition = confirm_response.json()["measurement_definition"]
    assert measurement_definition["auto_tuned"] is True
    assert measurement_definition["segmentation"]["threshold_mode"] == "fixed"


def test_setup_confirm_persists_wire_filtering_params_snapshot() -> None:
    client = TestClient(app)
    client.post("/api/camera/open", json={"profile": "dev_mock"})
    roi = {
        "center_x": 235.0,
        "center_y": 110.0,
        "width": 55.0,
        "height": 150.0,
        "angle_deg": 90.0,
        "coordinate_space": "acquisition",
    }

    confirm_response = client.post(
        "/api/setup/confirm",
        json={
            "name": "wire-param-snapshot",
            "target_family": "wire_strip",
            "roi": roi,
            "recipe_name": "wire_strip_default",
            "detector": {
                "detector_kind": "wire_strip_detector",
                "measurement_model": "blank_wire_bundle_envelope_blank",
                "measurement_mode": "wire_bundle_envelope",
                "min_quality": 0.6,
                "max_point_jump_px": 20.0,
                "reject_contact_on_roi_boundary": True,
                "boundary_margin_px": 3.0,
                "require_physical_endpoints": False,
                "skeleton_endpoint_detection": False,
                "preserve_visible_strip_contour": True,
                "min_interval_width_px": 4.0,
                "max_interval_width_ratio": 0.55,
                "min_valid_interval_count": 2,
                "min_local_contrast_score": 8.0,
                "max_internal_gap_ratio": 0.45,
                "min_neighbor_line_support": 1,
            },
        },
    )

    assert confirm_response.status_code == 200
    detector = confirm_response.json()["measurement_definition"]["detector"]
    assert detector["min_interval_width_px"] == 4.0
    assert detector["max_interval_width_ratio"] == 0.55
    assert detector["min_local_contrast_score"] == 8.0
    assert detector["max_internal_gap_ratio"] == 0.45


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


def _wire_bundle_with_remote_speck() -> np.ndarray:
    image = np.full((220, 320), 230, dtype=np.uint8)
    image[50:170, 64:72] = 30
    image[50:170, 98:108] = 30
    image[50:170, 134:148] = 30
    image[80:140, 262:268] = 30
    return image


def _wire_remote_speck_recipe(frame_ref: dict[str, object]) -> dict[str, object]:
    return {
        "frame_ref": frame_ref,
        "roi": {
            "center_x": 160.0,
            "center_y": 110.0,
            "width": 280.0,
            "height": 150.0,
            "angle_deg": 0.0,
            "coordinate_space": "acquisition",
        },
        "target_family": "wire_strip",
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
        "detector": {
            "detector_kind": "wire_strip_detector",
            "measurement_model": "blank_wire_bundle_envelope_blank",
            "measurement_mode": "wire_bundle_envelope",
            "min_quality": 0.6,
            "max_point_jump_px": 20.0,
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
        },
    }


def _decode_rgb_png(payload: bytes) -> tuple[int, int, np.ndarray]:
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    offset = 8
    width = height = None
    compressed = b""
    while offset < len(payload):
        chunk_length = struct.unpack(">I", payload[offset : offset + 4])[0]
        chunk_type = payload[offset + 4 : offset + 8]
        chunk_data = payload[offset + 8 : offset + 8 + chunk_length]
        offset += 12 + chunk_length
        if chunk_type == b"IHDR":
            width, height = struct.unpack(">II", chunk_data[:8])
        elif chunk_type == b"IDAT":
            compressed += chunk_data
        elif chunk_type == b"IEND":
            break
    assert width is not None
    assert height is not None
    raw = zlib.decompress(compressed)
    rows = np.frombuffer(raw, dtype=np.uint8).reshape(height, width * 3 + 1)
    assert np.all(rows[:, 0] == 0)
    pixels = rows[:, 1:].reshape(height, width, 3)
    return width, height, pixels
