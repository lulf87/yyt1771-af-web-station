from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from yyt1771_af.main import app


def _write_frame(path: Path, value: int) -> None:
    np.save(path, np.full((8, 12), value, dtype=np.uint8))


def _write_evaluation_output(output_dir: Path) -> None:
    output_dir.mkdir()
    samples = [
        {
            "frame_index": 0,
            "frame_name": "frame_000001.npy",
            "relative_time_s": 0.0,
            "status": "ok",
            "valid": True,
            "point_a": {"x": 2.0, "y": 3.0, "coordinate_space": "acquisition"},
            "point_b": {"x": 9.0, "y": 3.0, "coordinate_space": "acquisition"},
            "distance_px": 7.0,
            "quality": 0.9,
            "reason": "",
            "processing_ms": 1.0,
        },
        {
            "frame_index": 1,
            "frame_name": "frame_000002.npy",
            "relative_time_s": 0.1,
            "status": "ok",
            "valid": True,
            "point_a": {"x": 3.0, "y": 3.0, "coordinate_space": "acquisition"},
            "point_b": {"x": 10.0, "y": 3.0, "coordinate_space": "acquisition"},
            "distance_px": 7.0,
            "quality": 0.88,
            "reason": "",
            "processing_ms": 1.1,
        },
        {
            "frame_index": 2,
            "frame_name": "frame_000003.npy",
            "relative_time_s": 0.2,
            "status": "target_not_found",
            "valid": False,
            "point_a": None,
            "point_b": None,
            "distance_px": None,
            "quality": 0.1,
            "reason": "target_not_found",
            "processing_ms": 1.2,
        },
    ]
    (output_dir / "evaluation_samples.jsonl").write_text(
        "\n".join(json.dumps(sample) for sample in samples),
        encoding="utf-8",
    )
    (output_dir / "evaluation_summary.json").write_text(
        json.dumps(
            {
                "dataset_label": "api_fixture",
                "top_jump_frames": [{"frame_index": 1, "max_jump_px": 3.0}],
            }
        ),
        encoding="utf-8",
    )


def _open_payload(frames_dir: Path, output_dir: Path) -> dict[str, object]:
    return {
        "frames_dir": str(frames_dir),
        "evaluation_output_dir": str(output_dir),
        "dataset_label": "api_fixture",
        "target_family": "balloon_envelope",
        "roi": {
            "center_x": 6.0,
            "center_y": 4.0,
            "width": 8.0,
            "height": 4.0,
            "angle_deg": 0.0,
            "coordinate_space": "acquisition",
        },
        "fps": 10.0,
        "max_preview_width": 6,
    }


def _png_size(payload: bytes) -> tuple[int, int]:
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    return struct.unpack(">II", payload[16:24])


def test_offline_playback_open_reads_evaluation_samples_without_path_leak(
    tmp_path: Path,
) -> None:
    frames_dir = tmp_path / "private_frames"
    frames_dir.mkdir()
    for index in range(3):
        _write_frame(frames_dir / f"frame_{index + 1:06d}.npy", index + 1)
    evaluation_dir = tmp_path / "validation_results"
    _write_evaluation_output(evaluation_dir)
    client = TestClient(app)

    response = client.post(
        "/api/offline-playback/open",
        json=_open_payload(frames_dir, evaluation_dir),
    )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload)
    assert str(frames_dir) not in serialized
    assert str(evaluation_dir) not in serialized
    assert payload["opened"] is True
    assert payload["mode"] == "evaluation"
    assert payload["frame_count"] == 3
    assert payload["current_frame_index"] == 0
    assert payload["top_jump_frames"] == [1]
    assert payload["failure_frame_indices"] == [2]
    assert payload["current"]["frame_name"] == "frame_000001.npy"
    assert payload["current"]["display_width"] == 6
    assert payload["current"]["display_height"] == 4
    assert payload["current"]["detection"]["point_a"]["coordinate_space"] == "acquisition"
    assert payload["current"]["detection"]["detector"] == "balloon_envelope_detector:v1"


def test_offline_playback_seek_failure_frame_and_preview_png(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    for index in range(3):
        _write_frame(frames_dir / f"frame_{index + 1:06d}.npy", index + 1)
    evaluation_dir = tmp_path / "eval"
    _write_evaluation_output(evaluation_dir)
    client = TestClient(app)
    client.post("/api/offline-playback/open", json=_open_payload(frames_dir, evaluation_dir))

    seek_response = client.post("/api/offline-playback/seek", json={"frame_index": 2})
    png_response = client.get("/api/offline-playback/frame/2/preview.png?max_width=6")

    assert seek_response.status_code == 200
    frame = seek_response.json()
    assert frame["frame_index"] == 2
    assert frame["detection"]["valid"] is False
    assert frame["detection"]["point_a"] is None
    assert frame["detection"]["distance_px"] is None
    assert png_response.status_code == 200
    assert png_response.headers["content-type"] == "image/png"
    assert _png_size(png_response.content) == (6, 4)


def test_offline_playback_rejects_invalid_frame_index(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    _write_frame(frames_dir / "frame_000001.npy", 1)
    evaluation_dir = tmp_path / "eval"
    _write_evaluation_output(evaluation_dir)
    client = TestClient(app)
    client.post("/api/offline-playback/open", json=_open_payload(frames_dir, evaluation_dir))

    response = client.post("/api/offline-playback/seek", json={"frame_index": 99})

    assert response.status_code == 404
