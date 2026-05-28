from __future__ import annotations

import math

import numpy as np

from yyt1771_af.core.geometry import rotated_roi_corners
from yyt1771_af.core.models import Point2D, RotatedRoi
from yyt1771_af.report.simple_png import (
    draw_circle,
    draw_line,
    draw_polyline,
    draw_rect,
    draw_text,
    encode_png,
    grayscale_to_rgb,
)


def render_debug_overlay_png(
    *,
    frame: np.ndarray,
    roi: RotatedRoi,
    point_a: Point2D | None,
    point_b: Point2D | None,
    frame_index: int,
    status: str,
    distance_px: float | None,
    quality: float,
    reason: str | None,
) -> bytes:
    source = np.asarray(frame)
    height, width = source.shape[:2]
    pixels = grayscale_to_rgb(source)
    roi_points = [(int(round(point.x)), int(round(point.y))) for point in rotated_roi_corners(roi)]
    draw_polyline(pixels, width, [*roi_points, roi_points[0]], (24, 144, 255), thickness=2)

    if point_a is not None:
        draw_circle(pixels, width, int(round(point_a.x)), int(round(point_a.y)), 5, (255, 80, 80))
    if point_b is not None:
        draw_circle(pixels, width, int(round(point_b.x)), int(round(point_b.y)), 5, (80, 220, 120))
    if point_a is not None and point_b is not None:
        draw_line(
            pixels,
            width,
            int(round(point_a.x)),
            int(round(point_a.y)),
            int(round(point_b.x)),
            int(round(point_b.y)),
            (255, 214, 80),
            thickness=2,
        )

    label_height = 52
    draw_rect(pixels, width, 0, 0, min(width - 1, 760), label_height, (0, 0, 0))
    distance_text = (
        "-" if distance_px is None or not math.isfinite(distance_px) else f"{distance_px:.2f}"
    )
    reason_text = (reason or "")[:42]
    draw_text(
        pixels,
        width,
        8,
        8,
        f"FRAME:{frame_index} STATUS:{status} DIST:{distance_text} Q:{quality:.2f}",
        (255, 255, 255),
        scale=2,
    )
    if reason_text:
        draw_text(pixels, width, 8, 32, f"REASON:{reason_text}", (255, 220, 120), scale=2)

    return encode_png(width, height, pixels)
