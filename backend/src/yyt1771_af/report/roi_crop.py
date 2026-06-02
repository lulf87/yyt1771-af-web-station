from __future__ import annotations

import math

import numpy as np

from yyt1771_af.core.geometry import rotated_roi_corners
from yyt1771_af.core.models import RotatedRoi
from yyt1771_af.report.simple_png import encode_png, grayscale_to_rgb


def render_roi_crop_png(
    *,
    frame: np.ndarray,
    roi: RotatedRoi,
    scale: int = 1,
) -> bytes:
    if scale not in {1, 2, 4}:
        raise ValueError("ROI crop scale must be 1, 2, or 4")
    crop = roi_axis_aligned_crop(frame=frame, roi=roi)
    if scale > 1:
        crop = np.repeat(np.repeat(crop, scale, axis=0), scale, axis=1)
    height, width = crop.shape
    return encode_png(width, height, grayscale_to_rgb(crop))


def roi_axis_aligned_crop(*, frame: np.ndarray, roi: RotatedRoi) -> np.ndarray:
    source = np.asarray(frame)
    if source.ndim != 2:
        raise ValueError("ROI crop requires a 2D grayscale frame")
    height, width = source.shape
    corners = rotated_roi_corners(roi)
    min_x = max(0, int(math.floor(min(point.x for point in corners))))
    max_x = min(width, int(math.ceil(max(point.x for point in corners))))
    min_y = max(0, int(math.floor(min(point.y for point in corners))))
    max_y = min(height, int(math.ceil(max(point.y for point in corners))))
    if min_x >= max_x or min_y >= max_y:
        raise ValueError("ROI crop is outside frame")
    return np.clip(source[min_y:max_y, min_x:max_x], 0, 255).astype(np.uint8, copy=False)
