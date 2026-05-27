from __future__ import annotations

import math

from yyt1771_af.core.models import Point2D, RotatedRoi


def euclidean_distance(a: Point2D, b: Point2D) -> float:
    return math.hypot(b.x - a.x, b.y - a.y)


def roi_measurement_direction(angle_deg: float) -> tuple[float, float]:
    angle_rad = math.radians(angle_deg)
    return (math.cos(angle_rad), math.sin(angle_rad))


def rotated_roi_corners(roi: RotatedRoi) -> tuple[Point2D, Point2D, Point2D, Point2D]:
    half_width = roi.width / 2.0
    half_height = roi.height / 2.0
    cos_angle, sin_angle = roi_measurement_direction(roi.angle_deg)
    local_corners = (
        (-half_width, -half_height),
        (half_width, -half_height),
        (half_width, half_height),
        (-half_width, half_height),
    )

    return tuple(
        Point2D(
            x=roi.center_x + local_x * cos_angle - local_y * sin_angle,
            y=roi.center_y + local_x * sin_angle + local_y * cos_angle,
            coordinate_space=roi.coordinate_space,
        )
        for local_x, local_y in local_corners
    )


def roi_inside_frame(roi: RotatedRoi, frame_width: int, frame_height: int) -> bool:
    if frame_width <= 0 or frame_height <= 0:
        return False

    return all(
        0.0 <= corner.x <= frame_width and 0.0 <= corner.y <= frame_height
        for corner in rotated_roi_corners(roi)
    )
