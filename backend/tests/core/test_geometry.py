import pytest
from yyt1771_af.core.geometry import (
    euclidean_distance,
    roi_inside_frame,
    roi_measurement_direction,
    rotated_roi_corners,
)
from yyt1771_af.core.models import Point2D, RotatedRoi


def test_euclidean_distance_between_points() -> None:
    point_a = Point2D(x=0.0, y=0.0)
    point_b = Point2D(x=3.0, y=4.0)

    assert euclidean_distance(point_a, point_b) == 5.0


def test_roi_measurement_direction_uses_angle_degrees() -> None:
    direction = roi_measurement_direction(90.0)

    assert direction[0] == pytest.approx(0.0, abs=1e-12)
    assert direction[1] == pytest.approx(1.0)


def test_rotated_roi_corners_for_zero_degree_roi() -> None:
    roi = RotatedRoi(center_x=10.0, center_y=20.0, width=4.0, height=2.0, angle_deg=0.0)

    corners = rotated_roi_corners(roi)

    assert [(point.x, point.y) for point in corners] == [
        (8.0, 19.0),
        (12.0, 19.0),
        (12.0, 21.0),
        (8.0, 21.0),
    ]


def test_rotated_roi_corners_for_ninety_degree_roi() -> None:
    roi = RotatedRoi(center_x=10.0, center_y=20.0, width=4.0, height=2.0, angle_deg=90.0)

    corners = rotated_roi_corners(roi)

    assert [(round(point.x, 6), round(point.y, 6)) for point in corners] == [
        (11.0, 18.0),
        (11.0, 22.0),
        (9.0, 22.0),
        (9.0, 18.0),
    ]


def test_roi_inside_frame_rejects_outside_corners() -> None:
    roi = RotatedRoi(center_x=1.0, center_y=1.0, width=6.0, height=2.0, angle_deg=0.0)

    assert roi_inside_frame(roi, frame_width=20, frame_height=20) is False
