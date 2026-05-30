from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from yyt1771_af.camera.offline import (
    list_offline_frame_files,
    load_offline_frame,
    load_offline_frame_info,
)
from yyt1771_af.core.config import resolve_configured_path
from yyt1771_af.core.models import Frame, FrameRef, RotatedRoi
from yyt1771_af.core.path_redaction import safe_path_label, sanitize_path_metadata
from yyt1771_af.core.statuses import CoordinateSpace, TargetFamily
from yyt1771_af.services.frame_preview_service import (
    build_frame_preview_metadata,
    build_frame_preview_png,
)
from yyt1771_af.services.offline_datasets import resolve_offline_dataset_dir
from yyt1771_af.services.setup_service import (
    _detector_params_for_target,
    _segmentation_for_target,
    _serialize_detection_result,
)
from yyt1771_af.vision.detection import detect_target


class OfflinePlaybackOpenRequest(BaseModel):
    frames_dir: Path | None = None
    dataset_id: str | None = None
    target_family: TargetFamily
    roi: RotatedRoi
    fps: float = Field(default=10.0, gt=0.0)
    evaluation_output_dir: Path | None = None
    dataset_label: str | None = None
    recipe_name: str | None = None
    max_preview_width: int = Field(default=1200, gt=0, le=4096)


class OfflinePlaybackSeekRequest(BaseModel):
    frame_index: int = Field(ge=0)


class OfflinePlaybackStepRequest(BaseModel):
    failures_only: bool = False


class OfflinePlaybackFrameResponse(BaseModel):
    frame_index: int
    frame_name: str
    relative_time_s: float
    acquisition_width: int
    acquisition_height: int
    display_width: int
    display_height: int
    scale_x: float
    scale_y: float
    coordinate_space: CoordinateSpace = CoordinateSpace.ACQUISITION
    preview_url: str
    detection: dict[str, Any]


class OfflinePlaybackStatusResponse(BaseModel):
    opened: bool
    mode: str
    dataset_label: str | None
    frame_count: int
    current_frame_index: int | None
    top_jump_frames: list[int]
    failure_frame_indices: list[int]
    current: OfflinePlaybackFrameResponse | None = None


@dataclass(slots=True)
class _OfflinePlaybackSession:
    frames_dir: Path
    frame_paths: list[Path]
    target_family: TargetFamily
    roi: RotatedRoi
    fps: float
    dataset_label: str
    max_preview_width: int
    recipe_name: str | None = None
    mode: str = "live"
    evaluation_samples: dict[int, dict[str, Any]] = field(default_factory=dict)
    top_jump_frames: list[int] = field(default_factory=list)
    failure_frame_indices: list[int] = field(default_factory=list)
    current_frame_index: int = 0


class OfflinePlaybackService:
    def __init__(self) -> None:
        self._session: _OfflinePlaybackSession | None = None

    def open(self, request: OfflinePlaybackOpenRequest) -> OfflinePlaybackStatusResponse:
        frames_dir = _resolve_frames_dir(request.frames_dir, request.dataset_id)
        frame_paths = list_offline_frame_files(frames_dir)
        if not frame_paths:
            raise FileNotFoundError("offline playback frames directory has no supported frames")

        dataset_label = _safe_dataset_label(request.dataset_label, frames_dir)
        evaluation_samples: dict[int, dict[str, Any]] = {}
        top_jump_frames: list[int] = []
        failure_frame_indices: list[int] = []
        mode = "live"
        if request.evaluation_output_dir is not None:
            mode = "evaluation"
            evaluation_dir = resolve_configured_path(request.evaluation_output_dir)
            evaluation_samples = _read_evaluation_samples(evaluation_dir)
            top_jump_frames = _read_top_jump_frames(evaluation_dir)
            failure_frame_indices = sorted(
                frame_index
                for frame_index, sample in evaluation_samples.items()
                if sample.get("status") != "ok"
            )

        current_frame_index = min(evaluation_samples) if evaluation_samples else 0
        session = _OfflinePlaybackSession(
            frames_dir=frames_dir,
            frame_paths=frame_paths,
            target_family=request.target_family,
            roi=request.roi,
            fps=request.fps,
            dataset_label=dataset_label,
            max_preview_width=request.max_preview_width,
            recipe_name=request.recipe_name,
            mode=mode,
            evaluation_samples=evaluation_samples,
            top_jump_frames=top_jump_frames,
            failure_frame_indices=failure_frame_indices,
            current_frame_index=current_frame_index,
        )
        self._session = session
        return self.status(include_current=True)

    def status(self, *, include_current: bool = True) -> OfflinePlaybackStatusResponse:
        session = self._require_session()
        current = self.frame(session.current_frame_index) if include_current else None
        return OfflinePlaybackStatusResponse(
            opened=True,
            mode=session.mode,
            dataset_label=session.dataset_label,
            frame_count=len(session.frame_paths),
            current_frame_index=session.current_frame_index,
            top_jump_frames=session.top_jump_frames,
            failure_frame_indices=session.failure_frame_indices,
            current=current,
        )

    def seek(self, frame_index: int) -> OfflinePlaybackFrameResponse:
        session = self._require_session()
        self._path_for_index(session, frame_index)
        session.current_frame_index = frame_index
        return self.frame(frame_index)

    def next(self, *, failures_only: bool = False) -> OfflinePlaybackFrameResponse:
        session = self._require_session()
        frame_index = _next_index(
            current=session.current_frame_index,
            frame_count=len(session.frame_paths),
            candidates=session.failure_frame_indices if failures_only else None,
        )
        return self.seek(frame_index)

    def previous(self, *, failures_only: bool = False) -> OfflinePlaybackFrameResponse:
        session = self._require_session()
        frame_index = _previous_index(
            current=session.current_frame_index,
            candidates=session.failure_frame_indices if failures_only else None,
        )
        return self.seek(frame_index)

    def frame(self, frame_index: int) -> OfflinePlaybackFrameResponse:
        session = self._require_session()
        path = self._path_for_index(session, frame_index)
        info = load_offline_frame_info(path, frame_index=frame_index)
        preview_url = _playback_preview_url(frame_index, max_width=session.max_preview_width)
        metadata = build_frame_preview_metadata(
            frame_id=None,
            frame_index=frame_index,
            frame_name=info.frame_name,
            acquisition_width=info.width,
            acquisition_height=info.height,
            preview_url=preview_url,
            max_width=session.max_preview_width,
        )
        return OfflinePlaybackFrameResponse(
            frame_index=frame_index,
            frame_name=info.frame_name,
            relative_time_s=_relative_time_s(session, frame_index),
            acquisition_width=metadata.acquisition_width,
            acquisition_height=metadata.acquisition_height,
            display_width=metadata.display_width,
            display_height=metadata.display_height,
            scale_x=metadata.scale_x,
            scale_y=metadata.scale_y,
            coordinate_space=CoordinateSpace.ACQUISITION,
            preview_url=preview_url,
            detection=self._detection_for_frame(session, frame_index),
        )

    def preview_png(
        self,
        frame_index: int,
        *,
        max_width: int,
        max_height: int | None = None,
    ) -> bytes:
        session = self._require_session()
        path = self._path_for_index(session, frame_index)
        image = load_offline_frame(path)
        frame = Frame(
            frame_id=frame_index + 1,
            timestamp_ms=time.time_ns() // 1_000_000,
            width=int(image.shape[1]),
            height=int(image.shape[0]),
            coordinate_space=CoordinateSpace.ACQUISITION,
            image=image,
            frame_name=path.name,
            frame_index=frame_index,
            dtype=str(image.dtype),
        )
        return build_frame_preview_png(
            frame=frame,
            preview_url=_playback_preview_url(
                frame_index,
                max_width=max_width,
                max_height=max_height,
            ),
            max_width=max_width,
            max_height=max_height,
        ).png

    def _detection_for_frame(
        self,
        session: _OfflinePlaybackSession,
        frame_index: int,
    ) -> dict[str, Any]:
        if session.mode == "evaluation":
            sample = session.evaluation_samples.get(frame_index)
            if sample is None:
                raise IndexError("offline playback frame has no evaluation sample")
            return _evaluation_detection_payload(sample, target_family=session.target_family)

        path = self._path_for_index(session, frame_index)
        image = load_offline_frame(path)
        result = detect_target(
            frame=image,
            roi=session.roi,
            target_family=session.target_family,
            segmentation=_segmentation_for_target(session.target_family, session.recipe_name),
            params=_detector_params_for_target(session.target_family, session.recipe_name),
        )
        result.frame_ref = FrameRef(
            frame_id=frame_index + 1,
            timestamp_ms=time.time_ns() // 1_000_000,
            width=int(image.shape[1]),
            height=int(image.shape[0]),
            coordinate_space=CoordinateSpace.ACQUISITION,
        )
        return _serialize_detection_result(result).model_dump(mode="json")

    def _path_for_index(self, session: _OfflinePlaybackSession, frame_index: int) -> Path:
        if frame_index < 0 or frame_index >= len(session.frame_paths):
            raise IndexError("offline playback frame index is outside available frames")
        return session.frame_paths[frame_index]

    def _require_session(self) -> _OfflinePlaybackSession:
        if self._session is None:
            raise RuntimeError("offline playback is not opened")
        return self._session


def _resolve_frames_dir(frames_dir: Path | None, dataset_id: str | None = None) -> Path:
    if dataset_id is not None and dataset_id.strip() != "":
        return resolve_offline_dataset_dir(dataset_id)
    value = frames_dir or os.environ.get("YYT1771_AF_OFFLINE_DIR")
    if value is None:
        raise FileNotFoundError("YYT1771_AF_OFFLINE_DIR is required for offline playback")
    resolved = resolve_configured_path(Path(str(value)))
    if not resolved.exists() or not resolved.is_dir():
        raise FileNotFoundError("offline playback frames directory not found")
    return resolved


def _safe_dataset_label(dataset_label: str | None, frames_dir: Path) -> str:
    if dataset_label is None:
        return safe_path_label(str(frames_dir))
    sanitized = sanitize_path_metadata(dataset_label)
    if not isinstance(sanitized, str):
        return safe_path_label(str(frames_dir))
    return sanitized


def _read_evaluation_samples(evaluation_dir: Path) -> dict[int, dict[str, Any]]:
    samples_path = evaluation_dir / "evaluation_samples.jsonl"
    if not samples_path.exists():
        raise FileNotFoundError("evaluation_samples.jsonl is required for evaluation playback")
    samples: dict[int, dict[str, Any]] = {}
    for line in samples_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        sample = json.loads(line)
        samples[int(sample["frame_index"])] = sample
    if not samples:
        raise ValueError("evaluation_samples.jsonl does not contain any samples")
    return samples


def _read_top_jump_frames(evaluation_dir: Path) -> list[int]:
    for filename in ("evaluation_summary.json", "point_jump_summary.json"):
        path = evaluation_dir / filename
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        frames = payload.get("top_jump_frames", [])
        return [
            int(item["frame_index"])
            for item in frames
            if isinstance(item, dict) and "frame_index" in item
        ]
    return []


def _evaluation_detection_payload(
    sample: dict[str, Any],
    *,
    target_family: TargetFamily,
) -> dict[str, Any]:
    reason = sample.get("reason") or None
    return {
        "status": sample.get("status"),
        "valid": bool(sample.get("valid")),
        "point_a": sample.get("point_a"),
        "point_b": sample.get("point_b"),
        "distance_px": sample.get("distance_px"),
        "quality": float(sample.get("quality", 0.0)),
        "target_family": target_family.value,
        "detector": f"{_detector_params_for_target(target_family).detector_kind.value}:v1",
        "diagnostics": {"message": reason} if reason else {},
    }


def _relative_time_s(session: _OfflinePlaybackSession, frame_index: int) -> float:
    sample = session.evaluation_samples.get(frame_index)
    if sample is not None and sample.get("relative_time_s") is not None:
        return float(sample["relative_time_s"])
    return round(frame_index / session.fps, 6)


def _next_index(
    *,
    current: int,
    frame_count: int,
    candidates: list[int] | None,
) -> int:
    if candidates:
        for frame_index in candidates:
            if frame_index > current:
                return frame_index
        return candidates[-1]
    return min(frame_count - 1, current + 1)


def _previous_index(*, current: int, candidates: list[int] | None) -> int:
    if candidates:
        previous = [frame_index for frame_index in candidates if frame_index < current]
        return previous[-1] if previous else candidates[0]
    return max(0, current - 1)


def _playback_preview_url(
    frame_index: int,
    *,
    max_width: int,
    max_height: int | None = None,
) -> str:
    url = f"/api/offline-playback/frame/{frame_index}/preview.png?max_width={max_width}"
    if max_height is not None:
        url += f"&max_height={max_height}"
    return url


offline_playback_service = OfflinePlaybackService()
