from __future__ import annotations

import time

import numpy as np

from yyt1771_af.core.models import Frame
from yyt1771_af.core.statuses import CoordinateSpace


class MockCameraSource:
    source_type = "mock"

    def __init__(self) -> None:
        self._opened = False
        self._frame_counter = 0

    def open(self) -> None:
        self._opened = True

    def close(self) -> None:
        self._opened = False

    def get_latest_frame(self) -> Frame:
        if not self._opened:
            raise RuntimeError("mock camera source is not opened")

        self._frame_counter += 1
        image = _mock_setup_frame()
        return Frame(
            frame_id=self._frame_counter,
            timestamp_ms=time.time_ns() // 1_000_000,
            width=int(image.shape[1]),
            height=int(image.shape[0]),
            coordinate_space=CoordinateSpace.ACQUISITION,
            image=image,
        )


def _mock_setup_frame() -> np.ndarray:
    height = 220
    width = 320
    y, x = np.indices((height, width))
    image = np.full((height, width), 230, dtype=np.uint8)

    balloon_mask = ((x - 110.0) / 50.0) ** 2 + ((y - 110.0) / 25.0) ** 2 <= 1.0
    image[balloon_mask] = 30

    wire_center_x = 235.0
    wire_center_y = 110.0
    wire_length = 105.0
    wire_thickness = 18.0
    wire_mask = (np.abs(x - wire_center_x) <= wire_length / 2.0) & (
        np.abs(y - wire_center_y) <= wire_thickness / 2.0
    )
    image[wire_mask] = 30

    return image
