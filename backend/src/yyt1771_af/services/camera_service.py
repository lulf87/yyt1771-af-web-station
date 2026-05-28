from __future__ import annotations

import os
from collections import OrderedDict
from pathlib import Path

import numpy as np
from pydantic import BaseModel

from yyt1771_af.camera.base import CameraSource
from yyt1771_af.camera.mock import MockCameraSource
from yyt1771_af.camera.offline import OfflineFolderCameraSource
from yyt1771_af.core.config import load_camera_profile_config, resolve_configured_path
from yyt1771_af.core.models import Frame, FrameRef
from yyt1771_af.core.statuses import CoordinateSpace


class CameraOpenResult(BaseModel):
    opened: bool
    source_type: str


class CameraStatus(BaseModel):
    opened: bool
    source_type: str
    latest_frame_id: int | None = None
    frame_width: int | None = None
    frame_height: int | None = None
    coordinate_space: CoordinateSpace = CoordinateSpace.ACQUISITION


class CameraService:
    def __init__(self, *, max_cached_frames: int = 4) -> None:
        self._source: CameraSource | None = None
        self._source_type = "none"
        self._latest_frame: Frame | None = None
        self._frames: OrderedDict[int, Frame] = OrderedDict()
        self._pinned_frame_ids: set[int] = set()
        self._max_cached_frames = max(1, max_cached_frames)

    def open(self, profile: str) -> CameraOpenResult:
        self.close()
        self._source = self._source_for_profile(profile)
        self._source.open()
        self._source_type = getattr(self._source, "source_type", profile)
        self._latest_frame = self._initial_frame(self._source)
        self._cache_frame(self._latest_frame)
        return CameraOpenResult(opened=True, source_type=self._source_type)

    def close(self) -> None:
        if self._source is not None:
            self._source.close()
        self._source = None
        self._source_type = "none"
        self._latest_frame = None
        self._frames.clear()
        self._pinned_frame_ids.clear()

    def status(self) -> CameraStatus:
        return CameraStatus(
            opened=self._source is not None,
            source_type=self._source_type,
            latest_frame_id=self._latest_frame.frame_id if self._latest_frame is not None else None,
            frame_width=self._latest_frame.width if self._latest_frame is not None else None,
            frame_height=self._latest_frame.height if self._latest_frame is not None else None,
            coordinate_space=CoordinateSpace.ACQUISITION,
        )

    def get_latest_frame(self) -> Frame:
        if self._source is None:
            raise RuntimeError("camera source is not opened")
        self._latest_frame = self._source.get_latest_frame()
        self._cache_frame(self._latest_frame)
        return self._latest_frame

    def current_frame(self) -> Frame:
        if self._latest_frame is None:
            raise RuntimeError("camera source has no latest frame")
        return self._latest_frame

    def get_frame(self, frame_ref: FrameRef) -> Frame:
        frame = self._frames.get(frame_ref.frame_id)
        if frame is None:
            raise KeyError(f"frame {frame_ref.frame_id} is not available")
        self._frames.move_to_end(frame_ref.frame_id)
        if frame.width != frame_ref.width or frame.height != frame_ref.height:
            raise ValueError("frame geometry does not match requested frame reference")
        return frame

    @property
    def cached_frame_count(self) -> int:
        return len(self._frames)

    def pin_frame(self, frame_id: int) -> None:
        if frame_id not in self._frames:
            raise KeyError(f"frame {frame_id} is not available")
        self._pinned_frame_ids = {frame_id}
        self._trim_cache()

    def frame_ref(self, frame: Frame) -> FrameRef:
        return FrameRef(
            frame_id=frame.frame_id,
            timestamp_ms=frame.timestamp_ms,
            width=frame.width,
            height=frame.height,
            coordinate_space=CoordinateSpace.ACQUISITION,
        )

    def preview_svg(self, frame_id: int) -> str:
        frame = self._frames.get(frame_id)
        if frame is None:
            raise KeyError(f"frame {frame_id} is not available")
        return _frame_to_svg(frame.image)

    def _source_for_profile(self, profile: str) -> CameraSource:
        profile_reference = _profile_reference(profile)
        profile_config = load_camera_profile_config(profile_reference)
        camera_config = profile_config.camera
        camera_type = str(camera_config.get("type", profile_reference))
        if camera_type == "mock":
            return MockCameraSource()
        if camera_type == "offline_folder":
            folder_value = os.environ.get("YYT1771_AF_OFFLINE_DIR") or camera_config.get(
                "image_folder"
            )
            if folder_value is None:
                raise FileNotFoundError("YYT1771_AF_OFFLINE_DIR is required for dev_offline")
            loop_value = os.environ.get("YYT1771_AF_OFFLINE_LOOP")
            loop = (
                _truthy(loop_value) if loop_value is not None else bool(camera_config.get("loop"))
            )
            return OfflineFolderCameraSource(
                resolve_configured_path(Path(str(folder_value))),
                loop=loop,
            )
        raise ValueError(f"unsupported camera profile: {profile}")

    def _initial_frame(self, source: CameraSource) -> Frame:
        peek_frame = getattr(source, "peek_frame", None)
        if callable(peek_frame):
            return peek_frame()
        return source.get_latest_frame()

    def _cache_frame(self, frame: Frame) -> None:
        self._frames[frame.frame_id] = frame
        self._frames.move_to_end(frame.frame_id)
        self._trim_cache()

    def _trim_cache(self) -> None:
        while len(self._frames) > self._max_cached_frames:
            evictable_id = next(
                (frame_id for frame_id in self._frames if frame_id not in self._pinned_frame_ids),
                None,
            )
            if evictable_id is None:
                break
            self._frames.pop(evictable_id, None)


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _profile_reference(profile: str) -> str:
    return {"mock": "dev_mock", "offline": "dev_offline"}.get(profile, profile)


def _frame_to_svg(image: np.ndarray) -> str:
    frame = np.asarray(image)
    height, width = frame.shape[:2]
    dark_mask = frame < 128
    rects: list[str] = []
    for y in range(height):
        x = 0
        while x < width:
            if not dark_mask[y, x]:
                x += 1
                continue
            start_x = x
            while x < width and dark_mask[y, x]:
                x += 1
            rects.append(f'<rect x="{start_x}" y="{y}" width="{x - start_x}" height="1" />')

    rect_markup = "".join(rects)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="camera frame preview">'
        f'<rect width="{width}" height="{height}" fill="#e6edf3" />'
        f'<g fill="#202936">{rect_markup}</g>'
        "</svg>"
    )


camera_service = CameraService()
