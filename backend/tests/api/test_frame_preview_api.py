from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from yyt1771_af.main import app


def _png_size(payload: bytes) -> tuple[int, int]:
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    return struct.unpack(">II", payload[16:24])


def test_latest_frame_preview_returns_downsampled_metadata_without_local_paths(
    monkeypatch,
    tmp_path: Path,
) -> None:
    frames_dir = tmp_path / "private_frames"
    frames_dir.mkdir()
    np.save(frames_dir / "frame_000001.npy", np.arange(96, dtype=np.uint8).reshape(8, 12))
    monkeypatch.setenv("YYT1771_AF_OFFLINE_DIR", str(frames_dir))
    client = TestClient(app)

    assert client.post("/api/camera/open", json={"profile": "dev_offline"}).status_code == 200
    response = client.get("/api/camera/frame/latest?max_width=6")

    assert response.status_code == 200
    payload = response.json()
    assert payload["frame_name"] == "frame_000001.npy"
    assert payload["frame_index"] == 0
    assert payload["acquisition_width"] == 12
    assert payload["acquisition_height"] == 8
    assert payload["display_width"] == 6
    assert payload["display_height"] == 4
    assert payload["scale_x"] == 0.5
    assert payload["scale_y"] == 0.5
    assert payload["coordinate_space"] == "acquisition"
    assert payload["preview_url"].startswith("/api/camera/frame/")
    assert payload["preview_url"].endswith("/preview.png?max_width=6")
    assert str(frames_dir) not in json.dumps(payload)


def test_png_preview_endpoint_returns_downsampled_png(
    monkeypatch,
    tmp_path: Path,
) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    np.save(frames_dir / "frame_1.npy", np.arange(96, dtype=np.uint8).reshape(8, 12))
    monkeypatch.setenv("YYT1771_AF_OFFLINE_DIR", str(frames_dir))
    client = TestClient(app)
    client.post("/api/camera/open", json={"profile": "dev_offline"})
    frame_id = client.get("/api/camera/status").json()["latest_frame_id"]

    response = client.get(f"/api/camera/frame/{frame_id}/preview.png?max_width=6")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert _png_size(response.content) == (6, 4)


def test_png_preview_endpoint_rejects_unknown_cached_frame() -> None:
    client = TestClient(app)

    response = client.get("/api/camera/frame/999999/preview.png?max_width=6")

    assert response.status_code == 404
