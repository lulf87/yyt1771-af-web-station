from __future__ import annotations

import os
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from yyt1771_af.camera.offline import OfflineFolderCameraSource
from yyt1771_af.core.config import resolve_configured_path
from yyt1771_af.core.models import (
    DetectionDiagnostics,
    DetectionResult,
    Frame,
    FrameRef,
    MeasurementDefinition,
)
from yyt1771_af.core.path_redaction import safe_path_label, sanitize_path_metadata
from yyt1771_af.core.statuses import CoordinateSpace, DetectionStatus
from yyt1771_af.services.frame_preview_service import (
    build_frame_preview_metadata,
    build_frame_preview_png,
)
from yyt1771_af.services.setup_service import _serialize_detection_result, setup_service
from yyt1771_af.vision.detection import detect_target


class OfflineRunOpenRequest(BaseModel):
    measurement_definition_id: str
    frames_dir: Path | None = None
    fps: float = Field(default=10.0, gt=0.0)
    loop: bool = True
    dataset_label: str | None = None
    start_frame_index: int = Field(default=0, ge=0)
    max_preview_width: int = Field(default=1200, gt=0, le=4096)


class OfflineRunSeekRequest(BaseModel):
    frame_index: int = Field(ge=0)


class OfflineRunOpenResponse(BaseModel):
    session_id: str
    opened: bool
    dataset_label: str
    frame_count: int
    current_frame_index: int
    fps: float
    loop: bool
    measurement_definition_id: str


class OfflineRunStatusResponse(BaseModel):
    session_id: str
    opened: bool
    state: str
    dataset_label: str
    frame_count: int
    current_frame_index: int
    fps: float
    loop: bool
    measurement_definition_id: str
    latest: dict[str, Any] | None = None


class OfflineRunFrameResponse(BaseModel):
    session_id: str
    frame_index: int
    frame_name: str
    relative_time_s: float
    preview_url: str
    acquisition_width: int
    acquisition_height: int
    display_width: int
    display_height: int
    scale_x: float
    scale_y: float
    coordinate_space: CoordinateSpace = CoordinateSpace.ACQUISITION
    end_of_stream: bool = False
    detection: dict[str, Any]
    runtime: dict[str, Any]


class OfflineRunCloseResponse(BaseModel):
    session_id: str
    closed: bool


@dataclass(slots=True)
class OfflineRunSession:
    session_id: str
    source: OfflineFolderCameraSource
    frame_paths: list[Path]
    current_frame_index: int
    next_frame_index: int
    fps: float
    loop: bool
    dataset_label: str
    measurement_definition: MeasurementDefinition
    max_preview_width: int
    created_at_ms: int
    latest_frame_cache: OrderedDict[int, Frame] = field(default_factory=OrderedDict)
    latest_detection: dict[str, Any] | None = None
    end_of_stream: bool = False


class OfflineRunService:
    def __init__(self, *, max_cached_frames: int = 4) -> None:
        self._sessions: dict[str, OfflineRunSession] = {}
        self._max_cached_frames = max(1, max_cached_frames)

    def open(self, request: OfflineRunOpenRequest) -> OfflineRunOpenResponse:
        frames_dir = _resolve_frames_dir(request.frames_dir)
        source = OfflineFolderCameraSource(frames_dir, loop=request.loop)
        source.open()
        frame_paths = source.frame_paths
        if not frame_paths:
            raise FileNotFoundError("offline frames directory has no supported frames")
        if request.start_frame_index >= len(frame_paths):
            raise IndexError("offline run start frame index is outside available frames")

        measurement_definition = setup_service.get_measurement_definition(
            request.measurement_definition_id
        ).model_copy(deep=True)
        session_id = f"offline_run_{uuid4().hex[:12]}"
        dataset_label = _safe_dataset_label(request.dataset_label, frames_dir)
        session = OfflineRunSession(
            session_id=session_id,
            source=source,
            frame_paths=frame_paths,
            current_frame_index=request.start_frame_index,
            next_frame_index=request.start_frame_index,
            fps=request.fps,
            loop=request.loop,
            dataset_label=dataset_label,
            measurement_definition=measurement_definition,
            max_preview_width=request.max_preview_width,
            created_at_ms=time.time_ns() // 1_000_000,
        )
        self._sessions[session_id] = session
        return OfflineRunOpenResponse(
            session_id=session_id,
            opened=True,
            dataset_label=dataset_label,
            frame_count=len(frame_paths),
            current_frame_index=request.start_frame_index,
            fps=request.fps,
            loop=request.loop,
            measurement_definition_id=measurement_definition.measurement_definition_id,
        )

    def status(self, session_id: str) -> OfflineRunStatusResponse:
        session = self._require_session(session_id)
        state = "end_of_stream" if session.end_of_stream else "opened"
        return OfflineRunStatusResponse(
            session_id=session.session_id,
            opened=True,
            state=state,
            dataset_label=session.dataset_label,
            frame_count=len(session.frame_paths),
            current_frame_index=session.current_frame_index,
            fps=session.fps,
            loop=session.loop,
            measurement_definition_id=session.measurement_definition.measurement_definition_id,
            latest=session.latest_detection,
        )

    def next(self, session_id: str) -> OfflineRunFrameResponse:
        session = self._require_session(session_id)
        if session.end_of_stream:
            return self._frame_response(
                session,
                session.current_frame_index,
                end_of_stream=True,
            )

        frame_index = session.next_frame_index
        response = self._frame_response(session, frame_index, end_of_stream=False)
        session.current_frame_index = frame_index
        if frame_index >= len(session.frame_paths) - 1:
            if session.loop:
                session.next_frame_index = 0
            else:
                session.end_of_stream = True
        else:
            session.next_frame_index = frame_index + 1
        return response

    def previous(self, session_id: str) -> OfflineRunFrameResponse:
        session = self._require_session(session_id)
        if session.current_frame_index <= 0:
            frame_index = len(session.frame_paths) - 1 if session.loop else 0
        else:
            frame_index = session.current_frame_index - 1
        session.current_frame_index = frame_index
        session.next_frame_index = _next_index_after(
            frame_index,
            frame_count=len(session.frame_paths),
            loop=session.loop,
        )
        session.end_of_stream = False
        return self._frame_response(session, frame_index, end_of_stream=False)

    def seek(self, session_id: str, frame_index: int) -> OfflineRunFrameResponse:
        session = self._require_session(session_id)
        self._require_index(session, frame_index)
        session.current_frame_index = frame_index
        session.next_frame_index = _next_index_after(
            frame_index,
            frame_count=len(session.frame_paths),
            loop=session.loop,
        )
        session.end_of_stream = False
        return self._frame_response(session, frame_index, end_of_stream=False)

    def close(self, session_id: str) -> OfflineRunCloseResponse:
        session = self._require_session(session_id)
        session.source.close()
        self._sessions.pop(session_id, None)
        return OfflineRunCloseResponse(session_id=session_id, closed=True)

    def preview_png(
        self,
        session_id: str,
        frame_index: int,
        *,
        max_width: int,
        max_height: int | None = None,
    ) -> bytes:
        session = self._require_session(session_id)
        frame = self._read_frame(session, frame_index)
        return build_frame_preview_png(
            frame=frame,
            preview_url=_preview_url(
                session.session_id,
                frame_index,
                max_width=max_width,
                max_height=max_height,
            ),
            max_width=max_width,
            max_height=max_height,
        ).png

    def _frame_response(
        self,
        session: OfflineRunSession,
        frame_index: int,
        *,
        end_of_stream: bool,
    ) -> OfflineRunFrameResponse:
        frame = self._read_frame(session, frame_index)
        preview_url = _preview_url(
            session.session_id,
            frame_index,
            max_width=session.max_preview_width,
        )
        metadata = build_frame_preview_metadata(
            frame_id=frame.frame_id,
            frame_index=frame.frame_index,
            frame_name=frame.frame_name,
            acquisition_width=frame.width,
            acquisition_height=frame.height,
            preview_url=preview_url,
            max_width=session.max_preview_width,
        )
        detection = self._detect_frame(session, frame)
        runtime = {
            "run_mode": "live_offline",
            "recipe_locked": True,
            "source_type": "offline",
            "fps": session.fps,
            "loop": session.loop,
            "frame_index": frame_index,
            "frame_name": frame.frame_name,
            "relative_time_s": _relative_time_s(session, frame_index),
        }
        response = OfflineRunFrameResponse(
            session_id=session.session_id,
            frame_index=frame_index,
            frame_name=frame.frame_name or f"frame_{frame_index}",
            relative_time_s=_relative_time_s(session, frame_index),
            preview_url=preview_url,
            acquisition_width=metadata.acquisition_width,
            acquisition_height=metadata.acquisition_height,
            display_width=metadata.display_width,
            display_height=metadata.display_height,
            scale_x=metadata.scale_x,
            scale_y=metadata.scale_y,
            coordinate_space=CoordinateSpace.ACQUISITION,
            end_of_stream=end_of_stream,
            detection=detection,
            runtime=runtime,
        )
        session.latest_detection = response.model_dump(mode="json")
        return response

    def _detect_frame(
        self,
        session: OfflineRunSession,
        frame: Frame,
    ) -> dict[str, Any]:
        measurement_definition = session.measurement_definition
        frame_ref = FrameRef(
            frame_id=frame.frame_id,
            timestamp_ms=frame.timestamp_ms,
            width=frame.width,
            height=frame.height,
            coordinate_space=CoordinateSpace.ACQUISITION,
        )
        if (
            frame.width != measurement_definition.acquisition_frame_size.width
            or frame.height != measurement_definition.acquisition_frame_size.height
        ):
            result = DetectionResult(
                status=DetectionStatus.STALE_FRAME_GEOMETRY_MISMATCH,
                valid=False,
                point_a=None,
                point_b=None,
                distance_px=None,
                quality=0.0,
                target_family=measurement_definition.target_family,
                frame_ref=frame_ref,
                diagnostics=DetectionDiagnostics(
                    detector=measurement_definition.detector.detector_kind,
                    message="Frame dimensions differ from the confirmed measurement definition.",
                ),
            )
        else:
            result = detect_target(
                frame=frame.image,
                roi=measurement_definition.roi,
                target_family=measurement_definition.target_family,
                segmentation=measurement_definition.segmentation,
                params=measurement_definition.detector,
            )
            result.frame_ref = frame_ref
        return _serialize_detection_result(result).model_dump(mode="json")

    def _read_frame(self, session: OfflineRunSession, frame_index: int) -> Frame:
        self._require_index(session, frame_index)
        cached = session.latest_frame_cache.get(frame_index)
        if cached is not None:
            session.latest_frame_cache.move_to_end(frame_index)
            return cached
        frame = session.source.read_frame(frame_index)
        session.latest_frame_cache[frame_index] = frame
        session.latest_frame_cache.move_to_end(frame_index)
        while len(session.latest_frame_cache) > self._max_cached_frames:
            session.latest_frame_cache.popitem(last=False)
        return frame

    def _require_index(self, session: OfflineRunSession, frame_index: int) -> None:
        if frame_index < 0 or frame_index >= len(session.frame_paths):
            raise IndexError("offline run frame index is outside available frames")

    def _require_session(self, session_id: str) -> OfflineRunSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError("offline run session is not available")
        return session


def _resolve_frames_dir(frames_dir: Path | None) -> Path:
    value = frames_dir or os.environ.get("YYT1771_AF_OFFLINE_DIR")
    if value is None:
        raise FileNotFoundError("offline frames directory is not available")
    resolved = resolve_configured_path(Path(str(value)))
    if not resolved.exists() or not resolved.is_dir():
        raise FileNotFoundError("offline frames directory is not available")
    return resolved


def _safe_dataset_label(dataset_label: str | None, frames_dir: Path) -> str:
    if dataset_label is None:
        return safe_path_label(str(frames_dir))
    sanitized = sanitize_path_metadata(dataset_label)
    if not isinstance(sanitized, str) or sanitized.strip() == "":
        return safe_path_label(str(frames_dir))
    return sanitized


def _next_index_after(frame_index: int, *, frame_count: int, loop: bool) -> int:
    if frame_index >= frame_count - 1:
        return 0 if loop else frame_index
    return frame_index + 1


def _relative_time_s(session: OfflineRunSession, frame_index: int) -> float:
    return round(frame_index / session.fps, 6)


def _preview_url(
    session_id: str,
    frame_index: int,
    *,
    max_width: int,
    max_height: int | None = None,
) -> str:
    url = f"/api/offline-run/{session_id}/frame/{frame_index}/preview.png?max_width={max_width}"
    if max_height is not None:
        url += f"&max_height={max_height}"
    return url


offline_run_service = OfflineRunService()
