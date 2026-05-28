from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from yyt1771_af.services.offline_validation_service import inspect_offline_dataset


def _write_frame(path: Path, value: int, *, shape: tuple[int, int] = (6, 8)) -> None:
    np.save(path, np.full(shape, value, dtype=np.uint8))


def test_dataset_manifest_summarizes_npy_folder_without_absolute_path(tmp_path: Path) -> None:
    frames_dir = tmp_path / "private" / "frames"
    frames_dir.mkdir(parents=True)
    _write_frame(frames_dir / "frame_000001.npy", 10)
    _write_frame(frames_dir / "frame_000002.npy", 20)
    _write_frame(frames_dir / "frame_000004.npy", 30)

    manifest = inspect_offline_dataset(frames_dir, dataset_label="lab-capture")
    text = json.dumps(manifest, sort_keys=True)

    assert manifest["dataset_label"] == "lab-capture"
    assert manifest["frame_count"] == 3
    assert manifest["first_frame_name"] == "frame_000001.npy"
    assert manifest["last_frame_name"] == "frame_000004.npy"
    assert manifest["inferred_width"] == 8
    assert manifest["inferred_height"] == 6
    assert manifest["dtype"] == "uint8"
    assert manifest["estimated_bytes_per_frame"] == 48
    assert manifest["total_estimated_bytes"] == 144
    assert manifest["natural_sort_ok"] is True
    assert manifest["missing_index_count"] == 1
    assert manifest["invalid_file_count"] == 0
    assert manifest["sample_pixel_min"] == 10
    assert manifest["sample_pixel_max"] == 30
    assert manifest["sample_pixel_mean"] == 20.0
    assert manifest["local_path_redacted_label"] == "lab-capture"
    assert str(frames_dir) not in text
    assert "/private/" not in text


def test_dataset_manifest_redacts_unix_and_windows_paths() -> None:
    unix_manifest = inspect_offline_dataset(
        Path("/Users/lulingfeng/private/frames"),
        dataset_label="frames",
        allow_missing=True,
    )
    windows_manifest = inspect_offline_dataset(
        Path(r"C:\Users\lulingfeng\private\frames"),
        dataset_label="frames",
        allow_missing=True,
    )

    unix_text = json.dumps(unix_manifest, sort_keys=True)
    windows_text = json.dumps(windows_manifest, sort_keys=True)

    assert "/Users/" not in unix_text
    assert "private" not in unix_text
    assert r"C:\Users" not in windows_text
    assert "private" not in windows_text
