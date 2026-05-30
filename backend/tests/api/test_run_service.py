import json
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from yyt1771_af.main import app


def _confirm_balloon_definition(client: TestClient) -> str:
    client.post("/api/camera/open", json={"profile": "dev_mock"})
    response = client.post(
        "/api/setup/confirm",
        json={
            "name": "balloon-run",
            "target_family": "balloon_envelope",
            "roi": {
                "center_x": 110.0,
                "center_y": 110.0,
                "width": 130.0,
                "height": 80.0,
                "angle_deg": 0.0,
                "coordinate_space": "acquisition",
            },
            "recipe_name": "balloon_envelope_default",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["measurement_definition_id"].startswith("md_")
    assert payload["saved"] is True
    assert payload["measurement_definition"]["target_family"] == "balloon_envelope"
    assert payload["measurement_definition"]["roi"]["coordinate_space"] == "acquisition"
    assert payload["measurement_definition"]["coordinate_space"] == "acquisition"
    assert payload["measurement_definition"]["acquisition_frame_size"] == {
        "width": 320,
        "height": 220,
    }
    return payload["measurement_definition_id"]


def _confirm_wire_definition(client: TestClient) -> str:
    client.post("/api/camera/open", json={"profile": "dev_mock"})
    response = client.post(
        "/api/setup/confirm",
        json={
            "name": "wire-run",
            "target_family": "wire_strip",
            "roi": {
                "center_x": 235.0,
                "center_y": 110.0,
                "width": 55.0,
                "height": 150.0,
                "angle_deg": 90.0,
                "coordinate_space": "acquisition",
            },
            "recipe_name": "wire_strip_default",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["measurement_definition"]["target_family"] == "wire_strip"
    assert payload["measurement_definition"]["roi"]["coordinate_space"] == "acquisition"
    return payload["measurement_definition_id"]


def test_setup_confirm_creates_measurement_definition() -> None:
    client = TestClient(app)

    measurement_definition_id = _confirm_balloon_definition(client)

    assert measurement_definition_id


def test_run_start_rejects_unknown_measurement_definition(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    client = TestClient(app)
    client.post("/api/camera/open", json={"profile": "dev_mock"})

    response = client.post(
        "/api/runs/start",
        json={
            "measurement_definition_id": "md_not_confirmed",
            "sample_hz": 1000.0,
            "sample_count": 1,
        },
    )

    assert response.status_code == 409
    assert list(tmp_path.iterdir()) == []


def test_run_start_persists_metadata_definition_and_samples(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    client = TestClient(app)
    measurement_definition_id = _confirm_balloon_definition(client)

    start_response = client.post(
        "/api/runs/start",
        json={
            "measurement_definition_id": measurement_definition_id,
            "sample_hz": 10.0,
            "sample_count": 3,
        },
    )
    assert start_response.status_code == 200
    start_payload = start_response.json()
    run_id = start_payload["run_id"]
    assert start_payload["started"] is True
    assert start_payload["sample_count"] == 3

    run_dir = tmp_path / run_id
    assert (run_dir / "metadata.json").exists()
    assert (run_dir / "measurement_definition.json").exists()
    assert (run_dir / "samples.jsonl").exists()

    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["run_id"] == run_id
    assert metadata["sample_hz"] == 10.0
    assert metadata["status"] == "completed"
    assert metadata["temperature_source"]["source_type"] == "mock"

    sample_lines = (run_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(sample_lines) == 3
    sample_payloads = [json.loads(line) for line in sample_lines]
    timestamp_deltas = [
        next_sample["timestamp_ms"] - sample["timestamp_ms"]
        for sample, next_sample in zip(sample_payloads, sample_payloads[1:], strict=False)
    ]
    assert all(delta >= 90 for delta in timestamp_deltas)
    first_sample = json.loads(sample_lines[0])
    assert first_sample["run_id"] == run_id
    assert first_sample["sample_index"] == 0
    assert "timestamp_ms" in first_sample
    assert first_sample["temperature_c"] is not None
    assert first_sample["temperature_status"] == "ok"
    assert first_sample["temperature"]["temperature_c"] == first_sample["temperature_c"]
    assert first_sample["temperature"]["status"] == "ok"
    assert first_sample["temperature"]["source_type"] == "mock"
    assert first_sample["detection"]["status"] == "ok"
    assert first_sample["detection"]["point_a"] is not None
    assert first_sample["detection"]["point_b"] is not None
    assert first_sample["detection"]["point_a"]["coordinate_space"] == "acquisition"
    assert first_sample["detection"]["point_b"]["coordinate_space"] == "acquisition"
    assert first_sample["detection"]["distance_px"] is not None
    assert 0.0 <= first_sample["detection"]["quality"] <= 1.0

    samples_response = client.get(f"/api/runs/{run_id}/samples")
    assert samples_response.status_code == 200
    samples_payload = samples_response.json()
    assert samples_payload["run_id"] == run_id
    assert len(samples_payload["samples"]) == 3

    status_response = client.get(f"/api/runs/{run_id}/status")
    assert status_response.status_code == 200
    assert status_response.json()["sample_count"] == 3
    assert status_response.json()["temperature_source"]["source_type"] == "mock"

    stop_response = client.post(f"/api/runs/{run_id}/stop")
    assert stop_response.status_code == 200
    assert stop_response.json() == {"run_id": run_id, "stopped": True}


def test_balloon_run_uses_balloon_detector_for_every_sample(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    client = TestClient(app)
    measurement_definition_id = _confirm_balloon_definition(client)

    run_id = client.post(
        "/api/runs/start",
        json={
            "measurement_definition_id": measurement_definition_id,
            "sample_hz": 1000.0,
            "sample_count": 2,
        },
    ).json()["run_id"]

    samples = client.get(f"/api/runs/{run_id}/samples").json()["samples"]
    assert len(samples) == 2
    for sample in samples:
        detection = sample["detection"]
        assert detection["target_family"] == "balloon_envelope"
        assert detection["diagnostics"]["detector"] == "balloon_envelope_detector"
        assert detection["point_a"]["coordinate_space"] == "acquisition"
        assert detection["point_b"]["coordinate_space"] == "acquisition"


def test_run_uses_confirmed_detector_params_snapshot_instead_of_recipe_defaults(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    client = TestClient(app)
    client.post("/api/camera/open", json={"profile": "dev_mock"})
    confirm_response = client.post(
        "/api/setup/confirm",
        json={
            "name": "open-mesh-run",
            "target_family": "balloon_envelope",
            "roi": {
                "center_x": 110.0,
                "center_y": 110.0,
                "width": 130.0,
                "height": 80.0,
                "angle_deg": 0.0,
                "coordinate_space": "acquisition",
            },
            "recipe_name": "balloon_envelope_default",
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
        },
    )
    measurement_definition_id = confirm_response.json()["measurement_definition_id"]

    run_id = client.post(
        "/api/runs/start",
        json={
            "measurement_definition_id": measurement_definition_id,
            "sample_hz": 1000.0,
            "sample_count": 1,
        },
    ).json()["run_id"]

    measurement_definition = json.loads(
        (tmp_path / run_id / "measurement_definition.json").read_text(encoding="utf-8")
    )
    assert measurement_definition["detector"]["envelope_mode"] == "open_mesh"
    assert measurement_definition["detector"]["contact_source"] == "bridged_foreground"

    sample = client.get(f"/api/runs/{run_id}/samples").json()["samples"][0]
    diagnostics = sample["detection"]["diagnostics"]
    assert diagnostics["envelope_mode"] == "open_mesh"
    assert diagnostics["configured_contact_source"] == "bridged_foreground"
    assert diagnostics["contact_source_used"] == "bridged_foreground"


def test_wire_run_uses_wire_detector_for_every_sample(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    client = TestClient(app)
    measurement_definition_id = _confirm_wire_definition(client)

    run_id = client.post(
        "/api/runs/start",
        json={
            "measurement_definition_id": measurement_definition_id,
            "sample_hz": 1000.0,
            "sample_count": 2,
        },
    ).json()["run_id"]

    samples = client.get(f"/api/runs/{run_id}/samples").json()["samples"]
    assert len(samples) == 2
    for sample in samples:
        detection = sample["detection"]
        assert detection["target_family"] == "wire_strip"
        assert detection["diagnostics"]["detector"] == "wire_strip_detector"
        assert detection["point_a"]["coordinate_space"] == "acquisition"
        assert detection["point_b"]["coordinate_space"] == "acquisition"


def test_wire_run_applies_auto_tuned_recipe_without_retuning(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    client = TestClient(app)
    client.post("/api/camera/open", json={"profile": "dev_mock"})
    confirm_response = client.post(
        "/api/setup/confirm",
        json={
            "name": "auto-tuned-wire-run",
            "target_family": "wire_strip",
            "roi": {
                "center_x": 235.0,
                "center_y": 110.0,
                "width": 55.0,
                "height": 150.0,
                "angle_deg": 90.0,
                "coordinate_space": "acquisition",
            },
            "recipe_name": "wire_strip_default",
            "segmentation": {
                "polarity": "dark_on_light",
                "threshold_mode": "fixed",
                "threshold_value": 132,
                "blur_kernel": 3,
                "close_kernel": 3,
                "open_kernel": 1,
                "min_component_area_px": 30,
                "fill_internal_holes": False,
            },
            "auto_tuned": True,
        },
    )
    assert confirm_response.status_code == 200
    measurement_definition_id = confirm_response.json()["measurement_definition_id"]

    run_id = client.post(
        "/api/runs/start",
        json={
            "measurement_definition_id": measurement_definition_id,
            "sample_hz": 1000.0,
            "sample_count": 2,
        },
    ).json()["run_id"]

    measurement_definition = json.loads(
        (tmp_path / run_id / "measurement_definition.json").read_text(encoding="utf-8")
    )
    assert measurement_definition["auto_tuned"] is True
    assert measurement_definition["segmentation"]["threshold_mode"] == "fixed"
    assert measurement_definition["segmentation"]["threshold_value"] == 132

    samples = client.get(f"/api/runs/{run_id}/samples").json()["samples"]
    assert len(samples) == 2
    for sample in samples:
        diagnostics = sample["detection"]["diagnostics"]
        assert diagnostics["detector"] == "wire_strip_detector"
        assert diagnostics["threshold_mode"] == "fixed"


def test_run_samples_keep_invalid_status_without_fake_distance(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    client = TestClient(app)
    client.post("/api/camera/open", json={"profile": "dev_mock"})
    confirm_response = client.post(
        "/api/setup/confirm",
        json={
            "name": "invalid-wire-run",
            "target_family": "wire_strip",
            "roi": {
                "center_x": 235.0,
                "center_y": 110.0,
                "width": 8.0,
                "height": 150.0,
                "angle_deg": 90.0,
                "coordinate_space": "acquisition",
            },
            "recipe_name": "wire_strip_default",
        },
    )
    measurement_definition_id = confirm_response.json()["measurement_definition_id"]

    run_id = client.post(
        "/api/runs/start",
        json={
            "measurement_definition_id": measurement_definition_id,
            "sample_hz": 10.0,
            "sample_count": 2,
        },
    ).json()["run_id"]

    samples = client.get(f"/api/runs/{run_id}/samples").json()["samples"]
    assert len(samples) == 2
    for sample in samples:
        detection = sample["detection"]
        assert detection["status"] != "ok"
        assert detection["valid"] is False
        assert detection["distance_px"] is None
        assert detection["quality"] >= 0.0


def test_run_sample_records_temperature_status_when_temperature_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    monkeypatch.setenv("YYT1771_AF_TEMPERATURE_SOURCE", "none")
    client = TestClient(app)
    measurement_definition_id = _confirm_balloon_definition(client)

    run_id = client.post(
        "/api/runs/start",
        json={
            "measurement_definition_id": measurement_definition_id,
            "sample_hz": 1000.0,
            "sample_count": 1,
        },
    ).json()["run_id"]

    metadata = json.loads((tmp_path / run_id / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["temperature_source"]["source_type"] == "none"

    sample = client.get(f"/api/runs/{run_id}/samples").json()["samples"][0]
    assert sample["temperature_c"] is None
    assert sample["temperature_status"] == "unavailable"
    assert sample["temperature"]["temperature_c"] is None
    assert sample["temperature"]["status"] == "unavailable"
    assert sample["detection"]["distance_px"] is not None


def test_offline_source_can_confirm_and_run_without_camera_sdk(
    monkeypatch,
    tmp_path: Path,
) -> None:
    offline_dir = tmp_path / "offline"
    run_dir = tmp_path / "runs"
    offline_dir.mkdir()
    monkeypatch.setenv("YYT1771_AF_OFFLINE_DIR", str(offline_dir))
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(run_dir))

    height = 220
    width = 320
    y, x = np.indices((height, width))
    image = np.full((height, width), 230, dtype=np.uint8)
    balloon_mask = ((x - 110.0) / 50.0) ** 2 + ((y - 110.0) / 25.0) ** 2 <= 1.0
    image[balloon_mask] = 30
    np.save(offline_dir / "frame_001.npy", image)

    client = TestClient(app)
    open_response = client.post("/api/camera/open", json={"profile": "dev_offline"})
    assert open_response.status_code == 200
    assert open_response.json() == {"opened": True, "source_type": "offline"}

    confirm_response = client.post(
        "/api/setup/confirm",
        json={
            "name": "offline-balloon-run",
            "target_family": "balloon_envelope",
            "roi": {
                "center_x": 110.0,
                "center_y": 110.0,
                "width": 130.0,
                "height": 80.0,
                "angle_deg": 0.0,
                "coordinate_space": "acquisition",
            },
            "recipe_name": "balloon_envelope_default",
        },
    )
    measurement_definition_id = confirm_response.json()["measurement_definition_id"]

    start_response = client.post(
        "/api/runs/start",
        json={
            "measurement_definition_id": measurement_definition_id,
            "sample_hz": 1000.0,
            "sample_count": 1,
        },
    )
    assert start_response.status_code == 200
    run_id = start_response.json()["run_id"]
    metadata = json.loads((run_dir / run_id / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["source_type"] == "offline"

    sample = client.get(f"/api/runs/{run_id}/samples").json()["samples"][0]
    assert sample["detection"]["status"] == "ok"
    assert sample["detection"]["diagnostics"]["detector"] == "balloon_envelope_detector"
