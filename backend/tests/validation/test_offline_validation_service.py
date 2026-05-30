from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from yyt1771_af.core.models import RotatedRoi
from yyt1771_af.core.statuses import TargetFamily
from yyt1771_af.services.offline_validation_service import (
    OfflineThresholdSweepRequest,
    OfflineValidationRequest,
    OverlayPolicy,
    run_offline_threshold_sweep,
    run_offline_validation,
)


def _balloon_frame(
    *,
    center_x: float = 40.0,
    center_y: float = 30.0,
    width: int = 96,
    height: int = 72,
    target: int = 30,
    background: int = 230,
) -> np.ndarray:
    y, x = np.indices((height, width))
    image = np.full((height, width), background, dtype=np.uint8)
    mask = ((x - center_x) / 18.0) ** 2 + ((y - center_y) / 10.0) ** 2 <= 1.0
    image[mask] = target
    return image


def _write_sequence(frames_dir: Path, *, frame_count: int) -> None:
    frames_dir.mkdir(parents=True)
    for index in range(frame_count):
        np.save(frames_dir / f"frame_{index + 1:06d}.npy", _balloon_frame(center_x=40 + index))


def _request(
    frames_dir: Path,
    output_dir: Path,
    *,
    max_frames: int = 30,
) -> OfflineValidationRequest:
    return OfflineValidationRequest(
        frames_dir=frames_dir,
        target_family=TargetFamily.BALLOON_ENVELOPE,
        roi=RotatedRoi(
            center_x=42.0,
            center_y=30.0,
            width=60.0,
            height=36.0,
            angle_deg=0.0,
        ),
        fps=10.0,
        output_dir=output_dir,
        max_frames=max_frames,
        dataset_label="pytest-capture",
        overlay_policy=OverlayPolicy(first=2, every=None, failures=False, top_jumps=2),
    )


def test_offline_validation_runner_writes_manifest_samples_summary_and_curves(
    tmp_path: Path,
) -> None:
    frames_dir = tmp_path / "frames"
    output_dir = tmp_path / "validation"
    _write_sequence(frames_dir, frame_count=30)

    result = run_offline_validation(_request(frames_dir, output_dir, max_frames=30))

    assert result.processed_frames == 30
    assert (output_dir / "evaluation_manifest.json").exists()
    assert (output_dir / "evaluation_samples.csv").exists()
    assert (output_dir / "evaluation_samples.jsonl").exists()
    assert (output_dir / "evaluation_summary.json").exists()
    assert (output_dir / "distance_curve.png").read_bytes().startswith(b"\x89PNG")
    assert (output_dir / "quality_curve.png").read_bytes().startswith(b"\x89PNG")
    assert (output_dir / "status_histogram.png").read_bytes().startswith(b"\x89PNG")
    assert (output_dir / "point_jump_summary.json").exists()

    summary = json.loads((output_dir / "evaluation_summary.json").read_text(encoding="utf-8"))
    assert summary["dataset_label"] == "pytest-capture"
    assert summary["total_frames"] == 30
    assert summary["processed_frames"] == 30
    assert summary["valid_frames"] > 0
    assert summary["valid_ratio"] > 0
    assert summary["status_counts"]["ok"] == summary["valid_frames"]
    assert summary["mean_processing_ms"] is not None
    assert summary["effective_processing_fps"] is not None
    assert summary["point_a_jump_px_mean"] is not None
    assert summary["local_y_delta_px_max"] is not None
    assert summary["local_y_delta_px_max"] <= 1.0
    assert summary["parallel_error_px_max"] is not None
    assert summary["parallel_error_px_max"] <= 1.0
    assert summary["pattern_mismatch_count"] >= 0
    assert summary["object_interval_count_histogram"]
    assert summary["top_jump_frames"]

    sample_lines = (
        (output_dir / "evaluation_samples.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(sample_lines) == 30
    first_sample = json.loads(sample_lines[0])
    assert first_sample["frame_index"] == 0
    assert first_sample["frame_name"] == "frame_000001.npy"
    assert first_sample["relative_time_s"] == 0.0
    assert first_sample["point_a"]["coordinate_space"] == "acquisition"
    assert first_sample["distance_px"] is not None
    assert first_sample["diagnostics"]["measurement_line_y"] is not None
    assert first_sample["diagnostics"]["parallel_error_px"] <= 1.0


def test_offline_validation_records_invalid_frames_without_fake_distance(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    output_dir = tmp_path / "validation"
    frames_dir.mkdir()
    np.save(frames_dir / "frame_000001.npy", _balloon_frame())
    np.save(frames_dir / "frame_000002.npy", np.full((72, 96), 128, dtype=np.uint8))

    run_offline_validation(_request(frames_dir, output_dir, max_frames=2))

    samples = [
        json.loads(line)
        for line in (output_dir / "evaluation_samples.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert len(samples) == 2
    assert samples[1]["status"] != "ok"
    assert samples[1]["distance_px"] is None
    assert samples[1]["point_a"] is None
    assert samples[1]["point_b"] is None
    assert samples[1]["reason"]


def _wire_bundle_frame() -> np.ndarray:
    height, width = 180, 240
    center_x, center_y = 120.0, 90.0
    y, x = np.indices((height, width))
    dx = x.astype(float) - center_x
    dy = y.astype(float) - center_y
    wires = (
        ((dx >= -48.0) & (dx <= -42.0))
        | ((dx >= -14.0) & (dx <= -8.0))
        | ((dx >= 38.0) & (dx <= 46.0))
    ) & (np.abs(dy) <= 24.0)
    image = np.full((height, width), 230, dtype=np.uint8)
    image[wires] = 30
    return image


def test_offline_threshold_sweep_reports_per_threshold_stats(tmp_path: Path) -> None:
    frames_dir = tmp_path / "private" / "wire-frames"
    output_dir = tmp_path / "sweep"
    frames_dir.mkdir(parents=True)
    for index in range(4):
        np.save(frames_dir / f"frame_{index + 1:06d}.npy", _wire_bundle_frame())

    result = run_offline_threshold_sweep(
        OfflineThresholdSweepRequest(
            frames_dir=frames_dir,
            target_family=TargetFamily.WIRE_STRIP,
            roi=RotatedRoi(
                center_x=120.0,
                center_y=90.0,
                width=130.0,
                height=90.0,
                angle_deg=0.0,
            ),
            fps=10.0,
            output_dir=output_dir,
            candidate_thresholds=[100, 130, 160],
            dataset_label="pytest-wire",
        )
    )

    assert result.candidate_count == 3
    assert result.recommended_threshold_value in {100, 130, 160}
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["dataset_label"] == "pytest-wire"
    assert summary["target_family"] == "wire_strip"
    assert len(summary["candidates"]) == 3
    candidate = summary["candidates"][0]
    assert "valid_ratio" in candidate
    assert "formal_ab_span_px_mean" in candidate
    assert "broad_blob_rejection_mean" in candidate
    assert "distance_jump_px_max" in candidate
    assert str(frames_dir) not in result.summary_path.read_text(encoding="utf-8")
    assert "/private/" not in result.summary_path.read_text(encoding="utf-8")


def test_validation_artifacts_do_not_leak_absolute_paths(tmp_path: Path) -> None:
    frames_dir = tmp_path / "private" / "frames"
    output_dir = tmp_path / "validation"
    _write_sequence(frames_dir, frame_count=3)

    run_offline_validation(_request(frames_dir, output_dir, max_frames=3))

    manifest_text = (output_dir / "evaluation_manifest.json").read_text(encoding="utf-8")
    summary_text = (output_dir / "evaluation_summary.json").read_text(encoding="utf-8")

    assert str(frames_dir) not in manifest_text
    assert str(frames_dir) not in summary_text
    assert "/private/" not in manifest_text
    assert "/private/" not in summary_text
