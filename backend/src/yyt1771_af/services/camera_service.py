from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from pydantic import BaseModel

from yyt1771_af.camera.base import CameraSource
from yyt1771_af.camera.mock import MockCameraSource
from yyt1771_af.camera.offline import OfflineFolderCameraSource
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
    def __init__(self) -> None:
        self._source: CameraSource | None = None
        self._source_type = "none"
        self._latest_frame: Frame | None = None
        self._frames: dict[int, Frame] = {}

    def open(self, profile: str) -> CameraOpenResult:
        self.close()
        self._source = self._source_for_profile(profile)
        self._source.open()
        self._source_type = getattr(self._source, "source_type", profile)
        self._latest_frame = self._source.get_latest_frame()
        self._frames[self._latest_frame.frame_id] = self._latest_frame
        return CameraOpenResult(opened=True, source_type=self._source_type)

    def close(self) -> None:
        if self._source is not None:
            self._source.close()
        self._source = None
        self._source_type = "none"
        self._latest_frame = None
        self._frames.clear()

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
        self._frames[self._latest_frame.frame_id] = self._latest_frame
        return self._latest_frame

    def current_frame(self) -> Frame:
        if self._latest_frame is None:
            raise RuntimeError("camera source has no latest frame")
        return self._latest_frame

    def get_frame(self, frame_ref: FrameRef) -> Frame:
        frame = self._frames.get(frame_ref.frame_id)
        if frame is None:
            raise KeyError(f"frame {frame_ref.frame_id} is not available")
        if frame.width != frame_ref.width or frame.height != frame_ref.height:
            raise ValueError("frame geometry does not match requested frame reference")
        return frame

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
        if profile in {"dev_mock", "mock"}:
            return MockCameraSource()
        if profile in {"dev_offline", "offline"}:
            folder_value = os.environ.get("YYT1771_AF_OFFLINE_DIR")
            if folder_value is None:
                raise FileNotFoundError("YYT1771_AF_OFFLINE_DIR is required for dev_offline")
            return OfflineFolderCameraSource(Path(folder_value))
        raise ValueError(f"unsupported camera profile: {profile}")


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
