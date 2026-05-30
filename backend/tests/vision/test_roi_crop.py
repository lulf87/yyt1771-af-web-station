from __future__ import annotations

import numpy as np
from yyt1771_af.core.models import RotatedRoi
from yyt1771_af.core.statuses import CoordinateSpace
from yyt1771_af.vision.roi_ops import extract_roi_crop, rotated_roi_mask


def test_extract_roi_crop_limits_processing_to_local_window() -> None:
    frame = np.zeros((1364, 2048), dtype=np.uint8)
    roi = RotatedRoi(
        center_x=235.0,
        center_y=110.0,
        width=55.0,
        height=150.0,
        angle_deg=0.0,
        coordinate_space=CoordinateSpace.ACQUISITION,
    )

    crop = extract_roi_crop(frame, roi, padding_px=8)

    assert crop.frame.shape[0] < frame.shape[0]
    assert crop.frame.shape[1] < frame.shape[1]
    full_mask = rotated_roi_mask(frame.shape, roi)
    crop_mask = rotated_roi_mask(crop.frame.shape, crop.roi)
    y0 = max(0, crop.offset_y)
    x0 = max(0, crop.offset_x)
    y1 = min(frame.shape[0], crop.offset_y + crop.frame.shape[0])
    x1 = min(frame.shape[1], crop.offset_x + crop.frame.shape[1])
    cy0 = y0 - crop.offset_y
    cx0 = x0 - crop.offset_x
    assert np.array_equal(
        crop_mask[cy0 : cy0 + (y1 - y0), cx0 : cx0 + (x1 - x0)],
        full_mask[y0:y1, x0:x1],
    )
