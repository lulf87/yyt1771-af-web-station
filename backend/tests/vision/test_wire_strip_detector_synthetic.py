import math

import numpy as np
import pytest
import yyt1771_af.vision.wire_strip_detector as wire_strip_detector_module
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
        ((local_x >= -58.0) & (local_x <= -48.0))
        | ((local_x >= -10.0) & (local_x <= 0.0))
        | ((local_x >= 48.0) & (local_x <= 58.0))
    ) & (np.abs(local_y - 24.0) <= 8.0)
    image = np.full((180, 240), 230, dtype=np.uint8)
    image[center_line | wider_line] = 30
    return image


def _wire_bundle_with_low_contrast_remote_patch() -> tuple[np.ndarray, RotatedRoi]:
    roi = RotatedRoi(center_x=160.0, center_y=110.0, width=260.0, height=140.0, angle_deg=0.0)
    y, x = np.indices((220, 320))
    dx = x.astype(float) - roi.center_x
    dy = y.astype(float) - roi.center_y
    wires = (
        ((dx >= -100.0) & (dx <= -92.0))
        | ((dx >= -32.0) & (dx <= -24.0))
        | ((dx >= 36.0) & (dx <= 48.0))
    ) & (np.abs(dy) <= 42.0)
    low_contrast_patch = (dx >= 96.0) & (dx <= 112.0) & (np.abs(dy) <= 36.0)
    image = np.full((220, 320), 230, dtype=np.uint8)
    image[wires] = 30
    image[low_contrast_patch] = 223
    return image, roi


def _wire_bundle_with_high_contrast_remote_dot() -> tuple[np.ndarray, RotatedRoi]:
    roi = RotatedRoi(center_x=360.0, center_y=110.0, width=620.0, height=140.0, angle_deg=0.0)
    y, x = np.indices((220, 760))
    dx = x.astype(float) - roi.center_x
    dy = y.astype(float) - roi.center_y
    wires = (
        ((dx >= -55.0) & (dx <= -50.0))
        | ((dx >= -14.0) & (dx <= -7.0))
        | ((dx >= 1.0) & (dx <= 17.0))
        | ((dx >= 37.0) & (dx <= 46.0))
        | ((dx >= 52.0) & (dx <= 79.0))
    ) & (np.abs(dy) <= 42.0)
    remote_dot = (dx >= 252.0) & (dx <= 257.0) & (np.abs(dy) <= 8.0)
    image = np.full((220, 760), 230, dtype=np.uint8)
    image[wires | remote_dot] = 30
    return image, roi


def _wire_bundle_with_nearby_high_contrast_speck() -> tuple[np.ndarray, RotatedRoi]:
    roi = RotatedRoi(center_x=160.0, center_y=110.0, width=280.0, height=140.0, angle_deg=0.0)
    y, x = np.indices((220, 360))
    dx = x.astype(float) - roi.center_x
    dy = y.astype(float) - roi.center_y
    wires = (
        ((dx >= -55.0) & (dx <= -50.0))
        | ((dx >= -14.0) & (dx <= -7.0))
        | ((dx >= 1.0) & (dx <= 17.0))
        | ((dx >= 37.0) & (dx <= 46.0))
        | ((dx >= 52.0) & (dx <= 79.0))
    ) & (np.abs(dy) <= 42.0)
    # This speck is close enough to the real bundle that the 60px bundle-gap
    # threshold alone would merge it into the selected cluster.
    speck = (dx >= 128.0) & (dx <= 132.0) & (dy >= -2.0) & (dy <= 2.0)
    image = np.full((220, 360), 230, dtype=np.uint8)
    image[wires | speck] = 30
    return image, roi


def _wire_bundle_with_nearby_round_blob() -> tuple[np.ndarray, RotatedRoi]:
    roi = RotatedRoi(center_x=160.0, center_y=110.0, width=280.0, height=140.0, angle_deg=0.0)
    y, x = np.indices((220, 360))
    dx = x.astype(float) - roi.center_x
    dy = y.astype(float) - roi.center_y
    wires = (
        ((dx >= -55.0) & (dx <= -50.0))
        | ((dx >= -14.0) & (dx <= -7.0))
        | ((dx >= 1.0) & (dx <= 17.0))
        | ((dx >= 37.0) & (dx <= 46.0))
        | ((dx >= 52.0) & (dx <= 79.0))
    ) & (np.abs(dy) <= 42.0)
    round_blob = (dx >= 126.0) & (dx <= 134.0) & (dy >= -4.0) & (dy <= 4.0)
    image = np.full((220, 360), 230, dtype=np.uint8)
    image[wires | round_blob] = 30
    return image, roi


def _two_candidate_wire_bundle_frame(
    *,
    stronger_support: bool,
) -> tuple[np.ndarray, RotatedRoi]:
    roi = RotatedRoi(center_x=160.0, center_y=110.0, width=260.0, height=140.0, angle_deg=0.0)
    y, x = np.indices((220, 360))
    dx = x.astype(float) - roi.center_x
    dy = y.astype(float) - roi.center_y
    low_support = (
        ((dx >= -50.0) & (dx <= -46.0))
        | ((dx >= -3.0) & (dx <= 1.0))
        | ((dx >= 46.0) & (dx <= 50.0))
    ) & (np.abs(dy + 35.0) <= 34.0)
    high_support_intervals = (
        ((dx >= -49.0) & (dx <= -39.0))
        | ((dx >= -8.0) & (dx <= 4.0))
        | ((dx >= 39.0) & (dx <= 50.0))
    )
    high_support = high_support_intervals & (np.abs(dy - 35.0) <= 34.0)
    image = np.full((220, 360), 230, dtype=np.uint8)
    image[low_support | high_support] = 30
    if not stronger_support:
        ambiguous_copy = (
            ((dx >= -50.0) & (dx <= -46.0))
            | ((dx >= -3.0) & (dx <= 1.0))
            | ((dx >= 46.0) & (dx <= 50.0))
        ) & (np.abs(dy - 35.0) <= 34.0)
        image[high_support] = 230
        image[ambiguous_copy] = 30
    return image, roi


def _low_support_wide_bundle_frame() -> tuple[np.ndarray, RotatedRoi]:
    roi = RotatedRoi(center_x=160.0, center_y=110.0, width=220.0, height=140.0, angle_deg=0.0)
    y, x = np.indices((220, 360))
    dx = x.astype(float) - roi.center_x
    dy = y.astype(float) - roi.center_y
    wires = (
        ((dx >= -80.0) & (dx <= -75.0))
        | ((dx >= -2.5) & (dx <= 2.5))
        | ((dx >= 75.0) & (dx <= 80.0))
    ) & (np.abs(dy) <= 60.0)
    image = np.full((220, 360), 230, dtype=np.uint8)
    image[wires] = 30
    return image, roi


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
    assert result.diagnostics.point_a_source_interval == result.diagnostics.leftmost_valid_interval
    assert result.diagnostics.point_b_source_interval == result.diagnostics.rightmost_valid_interval
    assert result.diagnostics.point_a_source_interval in result.diagnostics.selected_valid_intervals
    assert result.diagnostics.point_b_source_interval in result.diagnostics.selected_valid_intervals
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


def _wire_bundle_with_broad_blob_frame() -> tuple[np.ndarray, RotatedRoi]:
    roi = RotatedRoi(center_x=120.0, center_y=90.0, width=160.0, height=120.0, angle_deg=0.0)
    y, x = np.indices((180, 240))
    dx = x.astype(float) - roi.center_x
    dy = y.astype(float) - roi.center_y
    wires = (
        (
            ((dx >= -60.0) & (dx <= -54.0))
            | ((dx >= -3.0) & (dx <= 3.0))
            | ((dx >= 54.0) & (dx <= 60.0))
        )
        & (dy >= -50.0)
        & (dy <= -10.0)
    )
    blob = (x >= 100) & (x <= 165) & (y >= 85) & (y <= 150)
    image = np.full((180, 240), 230, dtype=np.uint8)
    image[wires] = 30
    image[blob] = 120
    return image, roi


def _wire_bundle_with_inline_broad_blob_frame() -> tuple[np.ndarray, RotatedRoi]:
    roi = RotatedRoi(center_x=120.0, center_y=90.0, width=200.0, height=120.0, angle_deg=0.0)
    y, x = np.indices((180, 240))
    dx = x.astype(float) - roi.center_x
    dy = y.astype(float) - roi.center_y
    wires = (
        ((dx >= -93.0) & (dx <= -87.0))
        | ((dx >= -53.0) & (dx <= -47.0))
        | ((dx >= -13.0) & (dx <= -7.0))
    ) & (np.abs(dy) <= 40.0)
    blob = (dx >= 20.0) & (dx <= 95.0) & (np.abs(dy) <= 37.0)
    image = np.full((180, 240), 230, dtype=np.uint8)
    image[wires] = 30
    image[blob] = 120
    return image, roi


def test_wire_bundle_envelope_excludes_inline_broad_blob_from_formal_span() -> None:
    detector = WireStripDetector()
    frame, roi = _wire_bundle_with_inline_broad_blob_frame()

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
        params=WireStripDetectorParams(),
    )

    assert result.valid is True
    assert result.diagnostics.broad_blob_rejection_count >= 1
    a_local = _local_coordinates(result.point_a.x, result.point_a.y, roi)
    b_local = _local_coordinates(result.point_b.x, result.point_b.y, roi)
    # A/B stay on the wire bundle; the right-side broad blob is excluded.
    assert a_local[0] == pytest.approx(-93.0, abs=2.0)
    assert b_local[0] == pytest.approx(-7.0, abs=2.0)
    assert result.diagnostics.formal_ab_span_px is not None
    assert result.diagnostics.formal_ab_span_px == pytest.approx(86.0, abs=3.0)
    assert result.diagnostics.rejected_interval_reasons is not None
    assert "broad_blob" in result.diagnostics.rejected_interval_reasons


def test_wire_bundle_envelope_reports_phase1_diagnostics() -> None:
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

    assert result.valid is True
    assert result.diagnostics.threshold_mode == "fixed"
    assert result.diagnostics.configured_polarity == "dark_on_light"
    assert result.diagnostics.close_kernel == 1
    assert result.diagnostics.open_kernel == 1
    assert result.diagnostics.min_component_area_px == 20
    assert result.diagnostics.wire_likeness_score is not None
    assert result.diagnostics.component_aspect_ratio is not None
    assert result.diagnostics.component_orientation is not None
    assert result.diagnostics.neighbor_line_support is not None
    assert result.diagnostics.broad_blob_rejection_count == 0


def test_wire_bundle_envelope_flags_broad_background_blob_without_changing_ab() -> None:
    detector = WireStripDetector()
    frame, roi = _wire_bundle_with_broad_blob_frame()

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
        params=WireStripDetectorParams(),
    )

    assert result.valid is True
    assert result.diagnostics.broad_blob_rejection_count is not None
    assert result.diagnostics.broad_blob_rejection_count >= 1
    assert result.diagnostics.broad_blob_area_ratio is not None
    assert result.diagnostics.broad_blob_area_ratio >= 0.2
    a_local = _local_coordinates(result.point_a.x, result.point_a.y, roi)
    b_local = _local_coordinates(result.point_b.x, result.point_b.y, roi)
    assert a_local[0] == pytest.approx(-60.0, abs=1.5)
    assert b_local[0] == pytest.approx(60.0, abs=1.5)


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
    assert result.diagnostics.selected_line_rank == 1
    assert result.diagnostics.candidate_count is not None
    assert result.diagnostics.candidate_count >= 2
    assert result.diagnostics.top_candidate_lines is not None
    assert len(result.diagnostics.top_candidate_lines) >= 2
    assert result.diagnostics.selected_line_span_px == result.diagnostics.formal_ab_span_px
    assert result.diagnostics.second_best_span_px is not None
    assert result.diagnostics.span_margin_to_second_best_px is not None
    assert result.diagnostics.top_candidate_lines[0].formal_ab_span_px >= (
        result.diagnostics.top_candidate_lines[1].formal_ab_span_px
    )


def test_wire_bundle_envelope_rejects_low_contrast_remote_patch_as_b() -> None:
    detector = WireStripDetector()
    frame, roi = _wire_bundle_with_low_contrast_remote_patch()

    result = detector.detect(
        frame=frame,
        roi=roi,
        segmentation=SegmentationParams(
            polarity="dark_on_light",
            threshold_mode="fixed",
            threshold_value=225,
            close_kernel=1,
            open_kernel=1,
            min_component_area_px=20,
        ),
        params=WireStripDetectorParams(),
    )

    assert result.valid is True
    assert result.point_a is not None
    assert result.point_b is not None
    b_local = _local_coordinates(result.point_b.x, result.point_b.y, roi)
    assert b_local[0] == pytest.approx(48.0, abs=2.0)
    assert result.diagnostics.formal_ab_span_px == pytest.approx(148.0, abs=3.0)
    assert result.diagnostics.rejected_interval_reasons is not None
    assert "low_contrast" in result.diagnostics.rejected_interval_reasons


def test_wire_bundle_envelope_rejects_high_contrast_remote_interval_as_b() -> None:
    detector = WireStripDetector()
    frame, roi = _wire_bundle_with_high_contrast_remote_dot()

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
        params=WireStripDetectorParams(),
    )

    assert result.valid is True
    assert result.point_a is not None
    assert result.point_b is not None
    b_local = _local_coordinates(result.point_b.x, result.point_b.y, roi)
    assert b_local[0] == pytest.approx(79.0, abs=2.0)
    assert result.diagnostics.rightmost_valid_interval is not None
    assert result.diagnostics.rightmost_valid_interval.end_local_x == pytest.approx(79.0, abs=2.0)
    assert result.diagnostics.interval_gaps is not None
    assert max(result.diagnostics.interval_gaps) == pytest.approx(173.0, abs=2.0)
    assert result.diagnostics.bundle_cluster_count == 2
    assert result.diagnostics.selected_bundle_cluster_id == 0
    assert result.diagnostics.max_bundle_internal_gap_px == pytest.approx(60.0)
    assert result.diagnostics.rejected_remote_intervals is not None
    assert result.diagnostics.rejected_remote_intervals[-1].start_local_x == pytest.approx(
        252.0, abs=2.0
    )
    assert result.diagnostics.point_b_source_interval is not None
    assert (
        result.diagnostics.point_b_source_interval
        not in result.diagnostics.rejected_remote_intervals
    )
    assert result.diagnostics.remote_interval_rejection_count == 1
    assert result.diagnostics.rejected_remote_interval_reasons is not None
    assert "remote_gap_exceeded" in result.diagnostics.rejected_remote_interval_reasons
    assert result.diagnostics.top_candidate_lines is not None
    assert result.diagnostics.top_candidate_lines[0].selected_cluster_id == 0
    assert result.diagnostics.selected_line_support_ratio is not None
    assert result.diagnostics.selected_line_max_internal_gap_px is not None
    assert result.diagnostics.selected_line_interval_count is not None
    assert result.diagnostics.selected_line_interval_count >= 2


def test_wire_candidate_quality_gate_rejects_low_support_wide_cluster() -> None:
    detector = WireStripDetector()
    frame, roi = _low_support_wide_bundle_frame()

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
        params=WireStripDetectorParams(
            max_bundle_internal_gap_px=100.0,
            min_support_ratio=0.12,
        ),
    )

    assert result.valid is False
    assert result.status is DetectionStatus.QUALITY_BELOW_THRESHOLD
    assert result.point_a is None
    assert result.point_b is None
    assert result.distance_px is None
    assert result.diagnostics.top_candidate_lines is not None
    assert result.diagnostics.top_candidate_lines[0].rejected_reason == "support_ratio_below_min"


def test_wire_near_equal_spans_tie_break_by_support_ratio() -> None:
    detector = WireStripDetector()
    frame, roi = _two_candidate_wire_bundle_frame(stronger_support=True)

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
        params=WireStripDetectorParams(),
    )

    assert result.valid is True
    assert result.diagnostics.selected_line_reason == "span_tie_break_support_ratio"
    assert result.diagnostics.span_margin_to_second_best_px is not None
    assert result.diagnostics.span_margin_to_second_best_px <= 2.0
    assert result.diagnostics.selected_line_support_ratio is not None
    assert result.diagnostics.top_candidate_lines is not None
    selected = [
        candidate for candidate in result.diagnostics.top_candidate_lines if candidate.selected
    ]
    assert len(selected) == 1
    assert selected[0].support_ratio == result.diagnostics.selected_line_support_ratio
    assert result.diagnostics.measurement_line_y is not None
    assert result.diagnostics.measurement_line_y > 0.0


def test_wire_near_equal_low_quality_candidates_return_ambiguous() -> None:
    detector = WireStripDetector()
    frame, roi = _two_candidate_wire_bundle_frame(stronger_support=False)

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
        params=WireStripDetectorParams(),
    )

    assert result.valid is False
    assert result.status is DetectionStatus.CALIPER_CONTACT_AMBIGUOUS
    assert result.point_a is None
    assert result.point_b is None
    assert result.distance_px is None
    assert result.diagnostics.ambiguous_candidate_count is not None
    assert result.diagnostics.ambiguous_candidate_count >= 2
    assert result.diagnostics.top_candidate_lines is not None
    assert result.diagnostics.message is not None
    assert "ambiguous" in result.diagnostics.message


def test_wire_bundle_envelope_rejects_nearby_high_contrast_speck_as_b() -> None:
    detector = WireStripDetector()
    frame, roi = _wire_bundle_with_nearby_high_contrast_speck()

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
        params=WireStripDetectorParams(),
    )

    assert result.valid is True
    assert result.point_b is not None
    b_local = _local_coordinates(result.point_b.x, result.point_b.y, roi)
    assert b_local[0] == pytest.approx(79.0, abs=2.0)
    assert result.diagnostics.rightmost_valid_interval is not None
    assert result.diagnostics.rightmost_valid_interval.end_local_x == pytest.approx(79.0, abs=2.0)
    assert result.diagnostics.rejected_interval_reasons is not None
    assert "component_too_small" in result.diagnostics.rejected_interval_reasons


def test_wire_bundle_envelope_rejects_nearby_round_blob_as_b() -> None:
    detector = WireStripDetector()
    frame, roi = _wire_bundle_with_nearby_round_blob()

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
        params=WireStripDetectorParams(),
    )

    assert result.valid is True
    assert result.point_b is not None
    b_local = _local_coordinates(result.point_b.x, result.point_b.y, roi)
    assert b_local[0] == pytest.approx(79.0, abs=2.0)
    assert result.diagnostics.rejected_interval_reasons is not None
    assert "aspect_ratio_below_min" in result.diagnostics.rejected_interval_reasons


def test_wire_invariant_failure_preserves_source_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detector = WireStripDetector()
    roi = RotatedRoi(center_x=120.0, center_y=90.0, width=130.0, height=90.0, angle_deg=0.0)
    frame = _wire_bundle_frame(roi)

    monkeypatch.setattr(
        wire_strip_detector_module,
        "_source_boundary_on_foreground",
        lambda *args, **kwargs: False,
    )

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
        params=WireStripDetectorParams(),
    )

    assert result.valid is False
    assert result.status is DetectionStatus.COORDINATE_MAPPING_ERROR
    assert result.point_a is None
    assert result.point_b is None
    assert result.distance_px is None
    assert result.diagnostics.point_a_source_interval is not None
    assert result.diagnostics.point_b_source_interval is not None
    assert result.diagnostics.selected_bundle_cluster_id is not None
    assert result.diagnostics.selected_bundle_support_ratio is not None
    assert result.diagnostics.message is not None
    assert "point_a_not_foreground_boundary" in result.diagnostics.message


def test_wire_filtering_params_can_intentionally_allow_low_contrast_patch() -> None:
    detector = WireStripDetector()
    frame, roi = _wire_bundle_with_low_contrast_remote_patch()

    result = detector.detect(
        frame=frame,
        roi=roi,
        segmentation=SegmentationParams(
            polarity="dark_on_light",
            threshold_mode="fixed",
            threshold_value=225,
            close_kernel=1,
            open_kernel=1,
            min_component_area_px=20,
        ),
        params=WireStripDetectorParams(min_local_contrast_score=6.0),
    )

    assert result.valid is True
    assert result.point_b is not None
    b_local = _local_coordinates(result.point_b.x, result.point_b.y, roi)
    assert b_local[0] == pytest.approx(112.0, abs=2.0)
