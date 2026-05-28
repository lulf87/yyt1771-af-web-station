from __future__ import annotations

import csv
import json
import math
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import numpy as np

from yyt1771_af.camera.offline import (
    list_offline_frame_files,
    load_offline_frame,
    load_offline_frame_info,
    parsed_frame_index,
)
from yyt1771_af.core.config import load_detector_recipe_config
from yyt1771_af.core.geometry import euclidean_distance, roi_inside_frame
from yyt1771_af.core.models import (
    BalloonEnvelopeDetectorParams,
    DetectionDiagnostics,
    DetectionResult,
    Point2D,
    RotatedRoi,
    SegmentationParams,
    WireStripDetectorParams,
)
from yyt1771_af.core.path_redaction import safe_path_label, sanitize_path_metadata
from yyt1771_af.core.statuses import DetectionStatus, DetectorKind, TargetFamily
from yyt1771_af.report.debug_overlay import render_debug_overlay_png
from yyt1771_af.report.simple_png import (
    blank_rgb,
    draw_line,
    draw_rect,
    draw_text,
    encode_png,
)
from yyt1771_af.vision.detection import detect_target


@dataclass(frozen=True, slots=True)
class OverlayPolicy:
    first: int = 0
    every: int | None = None
    failures: bool = False
    top_jumps: int = 0


@dataclass(frozen=True, slots=True)
class OfflineValidationRequest:
    frames_dir: Path
    target_family: TargetFamily
    roi: RotatedRoi
    fps: float
    output_dir: Path
    max_frames: int | None = None
    start_frame: int = 0
    overlay_policy: OverlayPolicy = field(default_factory=OverlayPolicy)
    dataset_label: str | None = None
    recipe_name: str | None = None


@dataclass(frozen=True, slots=True)
class OfflineValidationResult:
    output_dir: Path
    summary_path: Path
    processed_frames: int
    valid_frames: int


SAMPLE_FIELDS = [
    "frame_index",
    "frame_name",
    "relative_time_s",
    "status",
    "point_a_x",
    "point_a_y",
    "point_b_x",
    "point_b_y",
    "distance_px",
    "quality",
    "reason",
    "processing_ms",
]


def inspect_offline_dataset(
    frames_dir: Path,
    *,
    dataset_label: str | None = None,
    allow_missing: bool = False,
) -> dict[str, Any]:
    label = dataset_label or safe_path_label(str(frames_dir))
    if not frames_dir.exists() or not frames_dir.is_dir():
        if not allow_missing:
            raise FileNotFoundError(f"offline frames directory not found: {frames_dir}")
        return {
            "dataset_label": label,
            "frame_count": 0,
            "first_frame_name": None,
            "last_frame_name": None,
            "inferred_width": None,
            "inferred_height": None,
            "dtype": None,
            "estimated_bytes_per_frame": None,
            "total_estimated_bytes": 0,
            "natural_sort_ok": True,
            "missing_index_count": 0,
            "invalid_file_count": 0,
            "sample_pixel_min": None,
            "sample_pixel_max": None,
            "sample_pixel_mean": None,
            "local_path_redacted_label": label,
        }

    frame_paths = list_offline_frame_files(frames_dir)
    infos = []
    invalid_file_count = 0
    for index, path in enumerate(frame_paths):
        try:
            infos.append(load_offline_frame_info(path, frame_index=index))
        except (OSError, ValueError):
            invalid_file_count += 1

    first_info = infos[0] if infos else None
    sample_stats = _sample_pixel_stats(frame_paths)
    parsed_indices = [parsed_frame_index(path) for path in frame_paths]
    numeric_indices = [index for index in parsed_indices if index is not None]
    natural_sort_ok = numeric_indices == sorted(numeric_indices)
    missing_index_count = _missing_index_count(numeric_indices)
    estimated_bytes_per_frame = first_info.nbytes if first_info is not None else None
    return sanitize_path_metadata(
        {
            "dataset_label": label,
            "frame_count": len(frame_paths),
            "first_frame_name": frame_paths[0].name if frame_paths else None,
            "last_frame_name": frame_paths[-1].name if frame_paths else None,
            "inferred_width": first_info.width if first_info is not None else None,
            "inferred_height": first_info.height if first_info is not None else None,
            "dtype": first_info.dtype if first_info is not None else None,
            "estimated_bytes_per_frame": estimated_bytes_per_frame,
            "total_estimated_bytes": (
                estimated_bytes_per_frame * len(frame_paths)
                if estimated_bytes_per_frame is not None
                else 0
            ),
            "natural_sort_ok": natural_sort_ok,
            "missing_index_count": missing_index_count,
            "invalid_file_count": invalid_file_count,
            "sample_pixel_min": sample_stats["min"],
            "sample_pixel_max": sample_stats["max"],
            "sample_pixel_mean": sample_stats["mean"],
            "local_path_redacted_label": label,
        }
    )


def run_offline_validation(request: OfflineValidationRequest) -> OfflineValidationResult:
    if request.fps <= 0.0:
        raise ValueError("fps must be positive")
    if request.start_frame < 0:
        raise ValueError("start_frame must be non-negative")
    if request.max_frames is not None and request.max_frames <= 0:
        raise ValueError("max_frames must be positive when provided")

    output_dir = request.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_label = request.dataset_label or safe_path_label(str(request.frames_dir))
    manifest = inspect_offline_dataset(request.frames_dir, dataset_label=dataset_label)
    _write_json(output_dir / "evaluation_manifest.json", manifest)

    frame_paths = list_offline_frame_files(request.frames_dir)
    selected_paths = frame_paths[request.start_frame :]
    if request.max_frames is not None:
        selected_paths = selected_paths[: request.max_frames]
    if not selected_paths:
        raise ValueError("no offline frames selected for validation")

    first_frame = load_offline_frame(selected_paths[0])
    if not roi_inside_frame(
        request.roi,
        frame_width=first_frame.shape[1] - 1,
        frame_height=first_frame.shape[0] - 1,
    ):
        raise ValueError("ROI is outside first frame bounds")
    recipe = load_detector_recipe_config(request.target_family, request.recipe_name)

    samples: list[dict[str, Any]] = []
    start_time = time.perf_counter()
    jsonl_path = output_dir / "evaluation_samples.jsonl"
    csv_path = output_dir / "evaluation_samples.csv"
    with (
        jsonl_path.open("w", encoding="utf-8") as jsonl_handle,
        csv_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as csv_handle,
    ):
        csv_writer = csv.DictWriter(csv_handle, fieldnames=SAMPLE_FIELDS)
        csv_writer.writeheader()
        for offset, frame_path in enumerate(selected_paths):
            frame_index = request.start_frame + offset
            sample = _evaluate_frame(
                frame_path=frame_path,
                frame_index=frame_index,
                relative_time_s=frame_index / request.fps,
                target_family=request.target_family,
                roi=request.roi,
                segmentation=recipe.segmentation,
                params=recipe.detector,
            )
            samples.append(sample)
            jsonl_handle.write(json.dumps(sample, separators=(",", ":")) + "\n")
            csv_writer.writerow(_csv_sample(sample))

    elapsed_s = time.perf_counter() - start_time
    point_jump_summary = _point_jump_summary(samples)
    summary = _summary(
        dataset_label=dataset_label,
        total_frames=manifest["frame_count"],
        samples=samples,
        elapsed_s=elapsed_s,
        point_jump_summary=point_jump_summary,
    )
    _write_json(output_dir / "evaluation_summary.json", summary)
    _write_json(output_dir / "point_jump_summary.json", point_jump_summary)
    _write_line_chart(
        output_dir / "distance_curve.png",
        samples,
        key="distance_px",
        title="DISTANCE PX",
    )
    _write_line_chart(output_dir / "quality_curve.png", samples, key="quality", title="QUALITY")
    _write_status_histogram(output_dir / "status_histogram.png", summary["status_counts"])
    _write_overlays(
        request=request,
        samples=samples,
        frame_paths=selected_paths,
        output_dir=output_dir,
        top_jump_frames=[int(item["frame_index"]) for item in summary["top_jump_frames"]],
    )
    return OfflineValidationResult(
        output_dir=output_dir,
        summary_path=output_dir / "evaluation_summary.json",
        processed_frames=len(samples),
        valid_frames=summary["valid_frames"],
    )


def _evaluate_frame(
    *,
    frame_path: Path,
    frame_index: int,
    relative_time_s: float,
    target_family: TargetFamily,
    roi: RotatedRoi,
    segmentation: SegmentationParams,
    params: BalloonEnvelopeDetectorParams | WireStripDetectorParams,
) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        frame = load_offline_frame(frame_path)
        result = detect_target(
            frame=frame,
            roi=roi,
            target_family=target_family,
            segmentation=segmentation,
            params=params,
        )
    except (OSError, ValueError) as exc:
        processing_ms = (time.perf_counter() - start) * 1000.0
        result = DetectionResult(
            status=DetectionStatus.SEGMENTATION_FAILED,
            valid=False,
            point_a=None,
            point_b=None,
            distance_px=None,
            quality=0.0,
            target_family=target_family,
            diagnostics=DetectionDiagnostics(
                detector=_detector_kind(target_family),
                message=str(exc),
            ),
        )
    else:
        processing_ms = (time.perf_counter() - start) * 1000.0
    reason = result.diagnostics.message or (
        result.status.value if result.status is not DetectionStatus.OK else ""
    )
    return {
        "frame_index": frame_index,
        "frame_name": frame_path.name,
        "relative_time_s": round(relative_time_s, 6),
        "status": result.status.value,
        "valid": result.valid,
        "point_a": result.point_a.model_dump(mode="json") if result.point_a is not None else None,
        "point_b": result.point_b.model_dump(mode="json") if result.point_b is not None else None,
        "distance_px": result.distance_px,
        "quality": result.quality,
        "reason": reason,
        "processing_ms": round(processing_ms, 6),
    }


def _detector_kind(target_family: TargetFamily) -> DetectorKind:
    if target_family is TargetFamily.BALLOON_ENVELOPE:
        return DetectorKind.BALLOON_ENVELOPE_DETECTOR
    return DetectorKind.WIRE_STRIP_DETECTOR


def _sample_pixel_stats(frame_paths: list[Path]) -> dict[str, float | int | None]:
    if not frame_paths:
        return {"min": None, "max": None, "mean": None}
    sample_indices = sorted({0, len(frame_paths) // 2, len(frame_paths) - 1})
    mins: list[int] = []
    maxes: list[int] = []
    means: list[float] = []
    for index in sample_indices:
        try:
            frame = load_offline_frame(frame_paths[index])
        except (OSError, ValueError):
            continue
        mins.append(int(np.min(frame)))
        maxes.append(int(np.max(frame)))
        means.append(float(np.mean(frame)))
    if not mins:
        return {"min": None, "max": None, "mean": None}
    return {
        "min": min(mins),
        "max": max(maxes),
        "mean": round(float(mean(means)), 6),
    }


def _missing_index_count(indices: list[int]) -> int:
    if not indices:
        return 0
    unique = sorted(set(indices))
    return max(0, unique[-1] - unique[0] + 1 - len(unique))


def _csv_sample(sample: dict[str, Any]) -> dict[str, Any]:
    point_a = sample["point_a"] or {}
    point_b = sample["point_b"] or {}
    return {
        "frame_index": sample["frame_index"],
        "frame_name": sample["frame_name"],
        "relative_time_s": sample["relative_time_s"],
        "status": sample["status"],
        "point_a_x": _blank_none(point_a.get("x")),
        "point_a_y": _blank_none(point_a.get("y")),
        "point_b_x": _blank_none(point_b.get("x")),
        "point_b_y": _blank_none(point_b.get("y")),
        "distance_px": _blank_none(sample["distance_px"]),
        "quality": sample["quality"],
        "reason": sample["reason"],
        "processing_ms": sample["processing_ms"],
    }


def _blank_none(value: Any) -> Any:
    return "" if value is None else value


def _point_jump_summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    previous: dict[str, Any] | None = None
    a_jumps: list[float] = []
    b_jumps: list[float] = []
    distance_jumps: list[float] = []
    top_jump_candidates: list[dict[str, Any]] = []
    for sample in samples:
        if not sample["valid"] or sample["point_a"] is None or sample["point_b"] is None:
            continue
        if previous is not None:
            point_a_jump = _point_distance(previous["point_a"], sample["point_a"])
            point_b_jump = _point_distance(previous["point_b"], sample["point_b"])
            distance_jump = abs(float(sample["distance_px"]) - float(previous["distance_px"]))
            a_jumps.append(point_a_jump)
            b_jumps.append(point_b_jump)
            distance_jumps.append(distance_jump)
            top_jump_candidates.append(
                {
                    "frame_index": sample["frame_index"],
                    "frame_name": sample["frame_name"],
                    "point_a_jump_px": round(point_a_jump, 6),
                    "point_b_jump_px": round(point_b_jump, 6),
                    "distance_jump_px": round(distance_jump, 6),
                    "max_jump_px": round(max(point_a_jump, point_b_jump, distance_jump), 6),
                }
            )
        previous = sample
    top_jump_candidates.sort(key=lambda item: item["max_jump_px"], reverse=True)
    return {
        "point_a_jump_px_mean": _mean_or_none(a_jumps),
        "point_a_jump_px_p95": _p95_or_none(a_jumps),
        "point_a_jump_px_max": _max_or_none(a_jumps),
        "point_b_jump_px_mean": _mean_or_none(b_jumps),
        "point_b_jump_px_p95": _p95_or_none(b_jumps),
        "point_b_jump_px_max": _max_or_none(b_jumps),
        "distance_jump_px_mean": _mean_or_none(distance_jumps),
        "distance_jump_px_p95": _p95_or_none(distance_jumps),
        "distance_jump_px_max": _max_or_none(distance_jumps),
        "top_jump_frames": top_jump_candidates[:20],
        "reason": (
            None if a_jumps else "Need at least two adjacent valid frames for jump statistics."
        ),
    }


def _summary(
    *,
    dataset_label: str,
    total_frames: int,
    samples: list[dict[str, Any]],
    elapsed_s: float,
    point_jump_summary: dict[str, Any],
) -> dict[str, Any]:
    status_counts = dict(sorted(Counter(sample["status"] for sample in samples).items()))
    failure_reasons = Counter(
        sample["reason"] for sample in samples if sample["status"] != DetectionStatus.OK.value
    )
    valid_samples = [
        sample for sample in samples if sample["valid"] and sample["distance_px"] is not None
    ]
    distances = [float(sample["distance_px"]) for sample in valid_samples]
    processing_times = [float(sample["processing_ms"]) for sample in samples]
    processed_frames = len(samples)
    valid_frames = len(valid_samples)
    invalid_frames = processed_frames - valid_frames
    return sanitize_path_metadata(
        {
            "dataset_label": dataset_label,
            "total_frames": total_frames,
            "processed_frames": processed_frames,
            "valid_frames": valid_frames,
            "invalid_frames": invalid_frames,
            "valid_ratio": round(valid_frames / processed_frames, 6) if processed_frames else 0.0,
            "status_counts": status_counts,
            "top_failure_reasons": [
                {"reason": reason, "count": count}
                for reason, count in failure_reasons.most_common(10)
            ],
            "mean_processing_ms": _mean_or_none(processing_times),
            "p95_processing_ms": _p95_or_none(processing_times),
            "effective_processing_fps": (
                round(processed_frames / elapsed_s, 6) if elapsed_s > 0.0 else None
            ),
            "distance_px_min": _min_or_none(distances),
            "distance_px_max": _max_or_none(distances),
            "distance_px_mean": _mean_or_none(distances),
            "distance_px_std": round(pstdev(distances), 6) if len(distances) >= 2 else None,
            **{key: point_jump_summary[key] for key in point_jump_summary if key != "reason"},
            "statistics_reason": point_jump_summary["reason"],
            "artifacts": {
                "manifest": "evaluation_manifest.json",
                "samples_csv": "evaluation_samples.csv",
                "samples_jsonl": "evaluation_samples.jsonl",
                "summary": "evaluation_summary.json",
                "distance_curve": "distance_curve.png",
                "quality_curve": "quality_curve.png",
                "status_histogram": "status_histogram.png",
                "point_jump_summary": "point_jump_summary.json",
                "overlays_dir": "overlays",
            },
        }
    )


def _point_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    return euclidean_distance(
        Point2D(x=float(a["x"]), y=float(a["y"])),
        Point2D(x=float(b["x"]), y=float(b["y"])),
    )


def _mean_or_none(values: list[float]) -> float | None:
    return round(float(mean(values)), 6) if values else None


def _p95_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = min(len(sorted_values) - 1, math.ceil(len(sorted_values) * 0.95) - 1)
    return round(float(sorted_values[index]), 6)


def _min_or_none(values: list[float]) -> float | None:
    return round(float(min(values)), 6) if values else None


def _max_or_none(values: list[float]) -> float | None:
    return round(float(max(values)), 6) if values else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(sanitize_path_metadata(payload), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _write_line_chart(path: Path, samples: list[dict[str, Any]], *, key: str, title: str) -> None:
    width = 900
    height = 420
    pixels = blank_rgb(width, height)
    draw_line(pixels, width, 60, 40, 60, 360, (100, 116, 139), thickness=1)
    draw_line(pixels, width, 60, 360, 840, 360, (100, 116, 139), thickness=1)
    draw_text(pixels, width, 64, 16, title, (15, 23, 42), scale=2)
    points = [
        (float(sample["frame_index"]), float(sample[key]))
        for sample in samples
        if sample.get(key) is not None and math.isfinite(float(sample[key]))
    ]
    if len(points) >= 2:
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        mapped = [
            (
                _map_value(x, min(xs), max(xs), 60, 840),
                _map_value(y, min(ys), max(ys), 360, 60),
            )
            for x, y in points
        ]
        for start, end in zip(mapped, mapped[1:], strict=False):
            draw_line(
                pixels,
                width,
                start[0],
                start[1],
                end[0],
                end[1],
                (20, 118, 110),
                thickness=2,
            )
    path.write_bytes(encode_png(width, height, pixels))


def _write_status_histogram(path: Path, status_counts: dict[str, int]) -> None:
    width = 900
    height = 420
    pixels = blank_rgb(width, height)
    draw_text(pixels, width, 64, 16, "STATUS HISTOGRAM", (15, 23, 42), scale=2)
    if status_counts:
        max_count = max(status_counts.values())
        bar_width = max(24, min(90, 680 // max(1, len(status_counts))))
        x = 80
        for status, count in status_counts.items():
            bar_height = int((count / max_count) * 240) if max_count else 0
            draw_rect(pixels, width, x, 340 - bar_height, x + bar_width, 340, (20, 118, 110))
            draw_text(pixels, width, x, 350, status[:10], (15, 23, 42), scale=1)
            draw_text(pixels, width, x, 330 - bar_height, str(count), (15, 23, 42), scale=1)
            x += bar_width + 18
    path.write_bytes(encode_png(width, height, pixels))


def _map_value(value: float, min_value: float, max_value: float, out_min: int, out_max: int) -> int:
    if abs(max_value - min_value) < 1e-9:
        return (out_min + out_max) // 2
    return int(
        round(out_min + ((value - min_value) / (max_value - min_value)) * (out_max - out_min))
    )


def _write_overlays(
    *,
    request: OfflineValidationRequest,
    samples: list[dict[str, Any]],
    frame_paths: list[Path],
    output_dir: Path,
    top_jump_frames: list[int],
) -> None:
    selected_indices = _selected_overlay_indices(request.overlay_policy, samples, top_jump_frames)
    if not selected_indices:
        return
    overlays_dir = output_dir / "overlays"
    overlays_dir.mkdir(parents=True, exist_ok=True)
    path_by_index = {request.start_frame + offset: path for offset, path in enumerate(frame_paths)}
    sample_by_index = {int(sample["frame_index"]): sample for sample in samples}
    for frame_index in sorted(selected_indices):
        frame_path = path_by_index.get(frame_index)
        sample = sample_by_index.get(frame_index)
        if frame_path is None or sample is None:
            continue
        try:
            frame = load_offline_frame(frame_path)
        except (OSError, ValueError):
            continue
        overlay = render_debug_overlay_png(
            frame=frame,
            roi=request.roi,
            point_a=Point2D.model_validate(sample["point_a"]) if sample["point_a"] else None,
            point_b=Point2D.model_validate(sample["point_b"]) if sample["point_b"] else None,
            frame_index=frame_index,
            status=sample["status"],
            distance_px=sample["distance_px"],
            quality=float(sample["quality"]),
            reason=sample["reason"],
        )
        (overlays_dir / f"overlay_{frame_index:06d}_{frame_path.stem}.png").write_bytes(overlay)


def _selected_overlay_indices(
    policy: OverlayPolicy,
    samples: list[dict[str, Any]],
    top_jump_frames: set[int],
) -> set[int]:
    selected: set[int] = set()
    if policy.first > 0:
        selected.update(int(sample["frame_index"]) for sample in samples[: policy.first])
    if policy.every is not None and policy.every > 0:
        selected.update(
            int(sample["frame_index"])
            for sample in samples
            if int(sample["frame_index"]) % policy.every == 0
        )
    if policy.failures:
        selected.update(
            int(sample["frame_index"])
            for sample in samples
            if sample["status"] != DetectionStatus.OK.value
        )
    if policy.top_jumps > 0:
        selected.update(top_jump_frames[: policy.top_jumps])
    return selected
