import math

import numpy as np
import pytest
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


def _wire_bundle_frame(
    roi: RotatedRoi,
    *,
    intervals: tuple[tuple[float, float], ...] = ((-48.0, -42.0), (-14.0, -8.0), (38.0, 46.0)),
    object_half_height: float = 24.0,
    background: int = 230,
    target: int = 30,
) -> np.ndarray:
    y, x = np.indices((180, 240))
    angle = math.radians(roi.angle_deg)
    unit_x = (math.cos(angle), math.sin(angle))
    unit_y = (-unit_x[1], unit_x[0])
    dx = x.astype(float) - roi.center_x
    dy = y.astype(float) - roi.center_y
    local_x = dx * unit_x[0] + dy * unit_x[1]
    local_y = dx * unit_y[0] + dy * unit_y[1]
    interval_masks = [(local_x >= start) & (local_x <= end) for start, end in intervals]
    mask = np.logical_or.reduce(interval_masks) & (np.abs(local_y) <= object_half_height)
    image = np.full((180, 240), background, dtype=np.uint8)
    image[mask] = target
    return image


def _variable_span_wire_bundle_frame(roi: RotatedRoi) -> np.ndarray:
    y, x = np.indices((180, 240))
    angle = math.radians(roi.angle_deg)
    unit_x = (math.cos(angle), math.sin(angle))
    unit_y = (-unit_x[1], unit_x[0])
    dx = x.astype(float) - roi.center_x
    dy = y.astype(float) - roi.center_y
    local_x = dx * unit_x[0] + dy * unit_x[1]
    local_y = dx * unit_y[0] + dy * unit_y[1]
    center_line = (
        ((local_x >= -32.0) & (local_x <= -12.0)) | ((local_x >= 12.0) & (local_x <= 32.0))
    ) & (np.abs(local_y) <= 8.0)
    wider_line = (
        ((local_x >= -58.0) & (local_x <= -48.0)) | ((local_x >= 48.0) & (local_x <= 58.0))
    ) & (np.abs(local_y - 24.0) <= 8.0)
    image = np.full((180, 240), 230, dtype=np.uint8)
    image[center_line | wider_line] = 30
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


def _wire_pair_roi(*, angle_deg: float = 0.0, width: float = 130.0) -> RotatedRoi:
    return RotatedRoi(
        center_x=120.0,
        center_y=90.0,
        width=width,
        height=90.0,
        angle_deg=angle_deg,
    )


def _local_coordinates(point_x: float, point_y: float, roi: RotatedRoi) -> tuple[float, float]:
    angle = math.radians(roi.angle_deg)
    unit_x = (math.cos(angle), math.sin(angle))
    unit_y = (-unit_x[1], unit_x[0])
    dx = point_x - roi.center_x
    dy = point_y - roi.center_y
    return (dx * unit_x[0] + dy * unit_x[1], dx * unit_y[0] + dy * unit_y[1])


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


def test_wire_bundle_envelope_returns_outer_boundaries_of_bundle_intervals() -> None:
    detector = WireStripDetector()
    roi = _wire_pair_roi(angle_deg=0.0)

    result = detector.detect(
        frame=_wire_bundle_frame(roi),
        roi=roi,
        segmentation=SegmentationParams(
            polarity="dark_on_light",
            threshold_mode="fixed",
            threshold_value=160,
            close_kernel=1,
            open_kernel=1,
            min_component_area_px=20,
        ),
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
    assert 92.0 <= result.distance_px <= 96.0
    assert result.diagnostics.measurement_mode == "wire_bundle_envelope"
    assert result.diagnostics.pattern_model == "blank_wire_bundle_envelope_blank"
    assert result.diagnostics.detected_pattern == "wire_bundle_envelope"
    assert result.diagnostics.object_interval_count == 3
    assert result.diagnostics.interval_count == 3
    assert result.diagnostics.bundle_outer_span_px == result.diagnostics.formal_ab_span_px
    assert result.diagnostics.point_a_on_foreground_boundary is True
    assert result.diagnostics.point_b_on_foreground_boundary is True
    assert result.diagnostics.leftmost_valid_interval is not None
    assert result.diagnostics.rightmost_valid_interval is not None
    a_local = _local_coordinates(result.point_a.x, result.point_a.y, roi)
    b_local = _local_coordinates(result.point_b.x, result.point_b.y, roi)
    assert abs(a_local[1] - b_local[1]) <= 1.0
    assert abs(a_local[1]) <= 1.0
    assert abs(b_local[1]) <= 1.0
    assert a_local[0] == pytest.approx(-48.0, abs=1.0)
    assert b_local[0] == pytest.approx(46.0, abs=1.0)


def test_rotated_wire_strip_returns_acquisition_contact_points() -> None:
    detector = WireStripDetector()
    roi = _wire_pair_roi(angle_deg=30.0)

    result = detector.detect(
        frame=_wire_bundle_frame(roi),
        roi=roi,
        segmentation=SegmentationParams(
            polarity="dark_on_light",
            threshold_mode="fixed",
            threshold_value=160,
            close_kernel=1,
            open_kernel=1,
            min_component_area_px=20,
        ),
        params=WireStripDetectorParams(),
    )

    assert result.status is DetectionStatus.OK
    assert result.valid is True
    assert result.point_a is not None
    assert result.point_b is not None
    assert result.point_a.coordinate_space is CoordinateSpace.ACQUISITION
    assert result.point_b.coordinate_space is CoordinateSpace.ACQUISITION
    assert result.distance_px is not None
    assert 92.0 <= result.distance_px <= 98.0
    assert result.diagnostics.parallel_error_px is not None
    assert result.diagnostics.parallel_error_px <= 1.0
    assert result.diagnostics.local_y_delta_px is not None
    assert result.diagnostics.local_y_delta_px <= 1.0
    assert result.diagnostics.measurement_mode == "wire_bundle_envelope"


def test_wire_strip_fails_when_contact_is_created_by_roi_boundary() -> None:
    detector = WireStripDetector()
    roi = _wire_pair_roi(angle_deg=0.0, width=100.0)
    frame = _wire_bundle_frame(roi, intervals=((-50.0, -42.0), (42.0, 50.0)))

    result = detector.detect(
        frame=frame,
        roi=roi,
        segmentation=SegmentationParams(
            polarity="dark_on_light",
            threshold_mode="fixed",
            threshold_value=160,
            close_kernel=1,
            open_kernel=1,
            min_component_area_px=20,
        ),
        params=WireStripDetectorParams(boundary_margin_px=3.0),
    )

    assert result.valid is False
    assert result.status is DetectionStatus.CALIPER_CONTACT_ON_ROI_BOUNDARY
    assert result.point_a is None
    assert result.point_b is None
    assert result.distance_px is None


def test_wire_bundle_envelope_fails_when_only_one_valid_interval_is_visible() -> None:
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
    assert result.status in {
        DetectionStatus.OBJECT_INTERVAL_COUNT_MISMATCH,
        DetectionStatus.PATTERN_NOT_FOUND,
    }
    assert result.point_a is None
    assert result.point_b is None
    assert result.distance_px is None


def test_wire_bundle_envelope_selects_current_frame_largest_span_without_previous_prior() -> None:
    detector = WireStripDetector()
    roi = _wire_pair_roi(angle_deg=0.0)

    result = detector.detect(
        frame=_variable_span_wire_bundle_frame(roi),
        roi=roi,
        segmentation=SegmentationParams(
            polarity="dark_on_light",
            threshold_mode="fixed",
            threshold_value=160,
            close_kernel=1,
            open_kernel=1,
            min_component_area_px=20,
        ),
        params=WireStripDetectorParams(),
    )

    assert result.status is DetectionStatus.OK
    assert result.point_a is not None
    assert result.point_b is not None
    assert result.diagnostics.formal_ab_span_px is not None
    assert result.diagnostics.formal_ab_span_px >= 115.0
    assert result.diagnostics.measurement_line_y is not None
    assert result.diagnostics.measurement_line_y >= 16.0
    assert result.diagnostics.previous_measurement_line_y is None
    assert result.diagnostics.line_y_delta_from_previous is None
