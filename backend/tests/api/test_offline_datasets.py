from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from yyt1771_af.main import app
from yyt1771_af.services.offline_datasets import (
    DATASETS_FILE_ENV,
    list_offline_datasets,
    resolve_offline_dataset_dir,
)


def _write_frame(path: Path) -> None:
    image = np.full((220, 320), 230, dtype=np.uint8)
    image[78:142, 58:164] = 30
    np.save(path, image)


def _write_datasets_config(
    config_path: Path,
    *,
    dataset_a: Path,
    dataset_b: Path,
) -> None:
    payload = {
        "datasets": [
            {"id": "material_a", "label": "Material A", "frames_dir": str(dataset_a)},
            {"id": "material_b", "label": "Material B", "frames_dir": str(dataset_b)},
        ]
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")


def test_registry_lists_and_resolves_configured_datasets(monkeypatch, tmp_path: Path) -> None:
    dataset_a = tmp_path / "20260522" / "frames"
    dataset_a.mkdir(parents=True)
    _write_frame(dataset_a / "frame_000001.npy")
    dataset_b = tmp_path / "20260529" / "frames"
    dataset_b.mkdir(parents=True)
    _write_frame(dataset_b / "frame_000001.npy")
    missing = tmp_path / "missing" / "frames"

    config_path = tmp_path / "offline_datasets.local.json"
    payload = {
        "datasets": [
            {"id": "material_a", "label": "Material A", "frames_dir": str(dataset_a)},
            {"id": "material_b", "label": "Material B", "frames_dir": str(dataset_b)},
            {"id": "material_c", "label": "Material C", "frames_dir": str(missing)},
        ]
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv(DATASETS_FILE_ENV, str(config_path))

    datasets = list_offline_datasets()
    ids = [dataset.dataset_id for dataset in datasets]
    assert ids == ["material_a", "material_b", "material_c"]
    assert resolve_offline_dataset_dir("material_a") == dataset_a
    assert resolve_offline_dataset_dir("material_b") == dataset_b


def test_datasets_endpoint_returns_labels_without_absolute_paths(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dataset_a = tmp_path / "20260522" / "frames"
    dataset_a.mkdir(parents=True)
    _write_frame(dataset_a / "frame_000001.npy")
    dataset_b = tmp_path / "20260529" / "frames"

    config_path = tmp_path / "offline_datasets.local.json"
    _write_datasets_config(config_path, dataset_a=dataset_a, dataset_b=dataset_b)
    monkeypatch.setenv(DATASETS_FILE_ENV, str(config_path))

    client = TestClient(app)
    response = client.get("/api/offline-run/datasets")
    assert response.status_code == 200
    payload = response.json()
    assert [item["dataset_id"] for item in payload] == ["material_a", "material_b"]
    assert payload[0]["available"] is True
    assert payload[1]["available"] is False
    serialized = json.dumps(payload)
    assert str(dataset_a) not in serialized
    assert str(dataset_b) not in serialized


def test_offline_run_open_uses_selected_dataset(monkeypatch, tmp_path: Path) -> None:
    from yyt1771_af.services.offline_run_service import (
        OfflineRunOpenRequest,
        offline_run_service,
    )

    dataset_a = tmp_path / "20260522" / "frames"
    dataset_a.mkdir(parents=True)
    _write_frame(dataset_a / "frame_000001.npy")
    dataset_b = tmp_path / "20260529" / "frames"
    dataset_b.mkdir(parents=True)
    _write_frame(dataset_b / "frame_000001.npy")
    _write_frame(dataset_b / "frame_000002.npy")

    config_path = tmp_path / "offline_datasets.local.json"
    _write_datasets_config(config_path, dataset_a=dataset_a, dataset_b=dataset_b)
    monkeypatch.setenv(DATASETS_FILE_ENV, str(config_path))

    client = TestClient(app)
    client.post("/api/camera/open", json={"profile": "dev_mock"})
    confirm = client.post(
        "/api/setup/confirm",
        json={
            "name": "dataset-pick",
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
        },
    )
    measurement_definition_id = confirm.json()["measurement_definition_id"]

    request = OfflineRunOpenRequest(
        measurement_definition_id=measurement_definition_id,
        dataset_id="material_b",
    )
    opened = offline_run_service.open(request)
    assert opened.opened is True
    assert opened.frame_count == 2
    offline_run_service.close(opened.session_id)
