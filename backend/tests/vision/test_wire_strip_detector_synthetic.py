import math

import numpy as np
from yyt1771_af.core.models import RotatedRoi, SegmentationParams, WireStripDetectorParams
from yyt1771_af.core.statuses import CoordinateSpace, DetectionStatus, DetectorKind, TargetFamily
from yyt1771_af.vision.wire_strip_detector import WireStripDetector


def _rotated_strip_frame(
    *,
    width: int = 240,
    height: int = 180,
    center: tuple[float, float] = (120.0, 90.0),
    length: float = 140.0,
    thickness: float = 20.0,
    angle_deg: float = 0.0,
    background: int = 230,
    target: int = 30,
) -> np.ndarray:
    mask = _rotated_strip_mask(
        width=width,
        height=height,
        center=center,
        length=length,
        thickness=thickness,
        angle_deg=angle_deg,
    )
    image = np.full((height, width), background, dtype=np.uint8)
    image[mask] = target
    return image


def _rotated_strip_mask(
    *,
    width: int = 240,
    height: int = 180,
    center: tuple[float, float] = (120.0, 90.0),
    length: float = 140.0,
    thickness: float = 20.0,
    angle_deg: float = 0.0,
) -> np.ndarray:
    y, x = np.indices((height, width))
    cx, cy = center
    angle = math.radians(angle_deg)
    tangent = (math.cos(angle), math.sin(angle))
    normal = (-math.sin(angle), math.cos(angle))
    dx = x - cx
    dy = y - cy
    tangent_distance = dx * tangent[0] + dy * tangent[1]
    normal_distance = dx * normal[0] + dy * normal[1]
    return (np.abs(tangent_distance) <= length / 2.0) & (np.abs(normal_distance) <= thickness / 2.0)


def _strip_roi(*, strip_angle_deg: float = 0.0, width: float = 58.0) -> RotatedRoi:
    return RotatedRoi(
        center_x=120.0,
        center_y=90.0,
        width=width,
        height=170.0,
        angle_deg=strip_angle_deg + 90.0,
    )


def _projection(point_x: float, point_y: float, angle_deg: float) -> float:
    angle = math.radians(angle_deg)
    return point_x * math.cos(angle) + point_y * math.sin(angle)


def _assert_point_on_strip_contour(point_x: float, point_y: float, *, angle_deg: float) -> None:
    mask = _rotated_strip_mask(angle_deg=angle_deg)
    x = int(round(point_x))
    y = int(round(point_y))
    assert mask[y, x]

    y_min = max(0, y - 1)
    y_max = min(mask.shape[0], y + 2)
    x_min = max(0, x - 1)
    x_max = min(mask.shape[1], x + 2)
    assert np.any(~mask[y_min:y_max, x_min:x_max])


def test_straight_wire_strip_returns_opposing_edge_contacts_not_endpoints() -> None:
    detector = WireStripDetector()
    roi = _strip_roi(strip_angle_deg=0.0)

    result = detector.detect(
        frame=_rotated_strip_frame(angle_deg=0.0),
        roi=roi,
        segmentation=SegmentationParams(close_kernel=5, open_kernel=1),
        params=WireStripDetectorParams(),
    )

    assert result.status is DetectionStatus.OK
    assert result.valid is True
    assert result.target_family is TargetFamily.WIRE_STRIP
    assert result.diagnostics.detector is DetectorKind.WIRE_STRIP_DETECTOR
    assert result.point_a is not None
    assert result.point_b is not None
    assert result.point_a.coordinate_space is CoordinateSpace.ACQUISITION
    assert result.point_b.coordinate_space is CoordinateSpace.ACQUISITION
    assert result.distance_px is not None
    assert 18.0 <= result.distance_px <= 23.0
    assert abs(result.point_a.x - 120.0) <= 2.0
    assert abs(result.point_b.x - 120.0) <= 2.0
    assert result.point_a.y < 83.0
    assert result.point_b.y > 97.0
    _assert_point_on_strip_contour(result.point_a.x, result.point_a.y, angle_deg=0.0)
    _assert_point_on_strip_contour(result.point_b.x, result.point_b.y, angle_deg=0.0)


def test_rotated_wire_strip_returns_acquisition_contact_points() -> None:
    detector = WireStripDetector()
    strip_angle = 30.0
    roi = _strip_roi(strip_angle_deg=strip_angle)

    result = detector.detect(
        frame=_rotated_strip_frame(angle_deg=strip_angle),
        roi=roi,
        segmentation=SegmentationParams(close_kernel=5, open_kernel=1),
        params=WireStripDetectorParams(),
    )

    assert result.status is DetectionStatus.OK
    assert result.valid is True
    assert result.point_a is not None
    assert result.point_b is not None
    assert result.point_a.coordinate_space is CoordinateSpace.ACQUISITION
    assert result.point_b.coordinate_space is CoordinateSpace.ACQUISITION
    projection_delta = _projection(result.point_b.x, result.point_b.y, roi.angle_deg) - _projection(
        result.point_a.x,
        result.point_a.y,
        roi.angle_deg,
    )
    assert 18.0 <= projection_delta <= 23.0
    assert result.distance_px is not None
    assert 18.0 <= result.distance_px <= 24.0
    _assert_point_on_strip_contour(
        result.point_a.x,
        result.point_a.y,
        angle_deg=strip_angle,
    )
    _assert_point_on_strip_contour(
        result.point_b.x,
        result.point_b.y,
        angle_deg=strip_angle,
    )


def test_wire_strip_fails_when_contact_is_created_by_roi_boundary() -> None:
    detector = WireStripDetector()
    frame = _rotated_strip_frame(thickness=70.0, angle_deg=0.0)

    result = detector.detect(
        frame=frame,
        roi=_strip_roi(strip_angle_deg=0.0, width=42.0),
        segmentation=SegmentationParams(close_kernel=5, open_kernel=1),
        params=WireStripDetectorParams(boundary_margin_px=3.0),
    )

    assert result.valid is False
    assert result.status is DetectionStatus.CALIPER_CONTACT_ON_ROI_BOUNDARY
    assert result.point_a is None
    assert result.point_b is None
    assert result.distance_px is None


def test_wire_strip_fails_when_only_one_opposing_contour_side_is_visible() -> None:
    detector = WireStripDetector()
    frame = np.full((180, 240), 230, dtype=np.uint8)
    frame[90, 50:190] = 30

    result = detector.detect(
        frame=frame,
        roi=_strip_roi(strip_angle_deg=0.0, width=8.0),
        segmentation=SegmentationParams(
            polarity="dark_on_light",
            close_kernel=1,
            open_kernel=1,
            min_component_area_px=20,
        ),
        params=WireStripDetectorParams(),
    )

    assert result.valid is False
    assert result.status is DetectionStatus.OPPOSING_CONTOUR_EDGES_MISSING
    assert result.point_a is None
    assert result.point_b is None
    assert result.distance_px is None
