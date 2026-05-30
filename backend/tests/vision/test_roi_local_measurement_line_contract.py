import math

import numpy as np
import pytest
from yyt1771_af.core.models import (
    BalloonEnvelopeDetectorParams,
    Point2D,
    RotatedRoi,
    SegmentationParams,
    WireStripDetectorParams,
)
from yyt1771_af.core.statuses import CoordinateSpace, DetectionStatus
from yyt1771_af.vision.balloon_envelope_detector import BalloonEnvelopeDetector
from yyt1771_af.vision.wire_strip_detector import WireStripDetector


def _local_to_acquisition(roi: RotatedRoi, local_x: float, local_y: float) -> tuple[float, float]:
    angle = math.radians(roi.angle_deg)
    unit_x = (math.cos(angle), math.sin(angle))
    unit_y = (-unit_x[1], unit_x[0])
    return (
        roi.center_x + local_x * unit_x[0] + local_y * unit_y[0],
        roi.center_y + local_x * unit_x[1] + local_y * unit_y[1],
    )


def _acquisition_to_local(roi: RotatedRoi, point: Point2D) -> tuple[float, float]:
    angle = math.radians(roi.angle_deg)
    unit_x = (math.cos(angle), math.sin(angle))
    unit_y = (-unit_x[1], unit_x[0])
    dx = point.x - roi.center_x
    dy = point.y - roi.center_y
    return (dx * unit_x[0] + dy * unit_x[1], dx * unit_y[0] + dy * unit_y[1])


def _foreground_from_local_predicate(
    roi: RotatedRoi,
    *,
    predicate,
    width: int = 260,
    height: int = 220,
) -> np.ndarray:
    y, x = np.indices((height, width))
    angle = math.radians(roi.angle_deg)
    unit_x = (math.cos(angle), math.sin(angle))
    unit_y = (-unit_x[1], unit_x[0])
    dx = x.astype(float) - roi.center_x
    dy = y.astype(float) - roi.center_y
    local_x = dx * unit_x[0] + dy * unit_x[1]
    local_y = dx * unit_y[0] + dy * unit_y[1]
    mask = predicate(local_x, local_y)
    image = np.full((height, width), 230, dtype=np.uint8)
    image[mask] = 30
    return image


def _single_object_frame(roi: RotatedRoi) -> np.ndarray:
    return _foreground_from_local_predicate(
        roi,
        predicate=lambda local_x, local_y: (np.abs(local_x) <= 46.0) & (np.abs(local_y) <= 16.0),
    )


def _skewed_single_object_frame(roi: RotatedRoi) -> np.ndarray:
    return _foreground_from_local_predicate(
        roi,
        predicate=lambda local_x, local_y: (
            (local_y >= -22.0)
            & (local_y <= 22.0)
            & (local_x >= (-42.0 + 0.55 * local_y))
            & (local_x <= (42.0 + 0.55 * local_y))
        ),
    )


def _two_object_frame(roi: RotatedRoi) -> np.ndarray:
    return _foreground_from_local_predicate(
        roi,
        predicate=lambda local_x, local_y: (
            (((local_x >= -52.0) & (local_x <= -28.0)) | ((local_x >= 28.0) & (local_x <= 52.0)))
            & (np.abs(local_y) <= 14.0)
        ),
    )


def _open_mesh_frame(roi: RotatedRoi) -> np.ndarray:
    mesh_intervals = [(-56.0, -48.0), (-24.0, -16.0), (8.0, 16.0), (44.0, 56.0)]
    return _foreground_from_local_predicate(
        roi,
        predicate=lambda local_x, local_y: (
            np.logical_or.reduce(
                [(local_x >= start) & (local_x <= end) for start, end in mesh_intervals]
            )
            & (np.abs(local_y) <= 8.0)
        ),
    )


def _open_mesh_with_right_debug_only_fill_frame(roi: RotatedRoi) -> np.ndarray:
    return _foreground_from_local_predicate(
        roi,
        predicate=lambda local_x, local_y: (
            ((local_x >= -54.0) & (local_x <= -24.0)) & (np.abs(local_y) <= 18.0)
        ),
    )


def _segmentation() -> SegmentationParams:
    return SegmentationParams(
        polarity="dark_on_light",
        threshold_mode="fixed",
        threshold_value=160,
        close_kernel=1,
        open_kernel=1,
        min_component_area_px=20,
        fill_internal_holes=False,
    )


def _assert_same_local_measurement_line(
    roi: RotatedRoi,
    point_a: Point2D,
    point_b: Point2D,
    diagnostics: object,
    *,
    tolerance_px: float = 1.0,
) -> None:
    a_local = _acquisition_to_local(roi, point_a)
    b_local = _acquisition_to_local(roi, point_b)
    assert point_a.coordinate_space is CoordinateSpace.ACQUISITION
    assert point_b.coordinate_space is CoordinateSpace.ACQUISITION
    assert abs(a_local[1] - b_local[1]) <= tolerance_px
    assert diagnostics.point_a_local is not None
    assert diagnostics.point_b_local is not None
    assert diagnostics.measurement_line_y is not None
    assert diagnostics.local_y_delta_px is not None
    assert diagnostics.local_y_delta_px <= tolerance_px
    assert diagnostics.parallel_error_px is not None
    assert diagnostics.parallel_error_px <= tolerance_px
    assert diagnostics.chord_length_px is not None


@pytest.mark.parametrize("angle_deg", [0.0, 90.0, 30.0])
def test_balloon_ab_points_are_same_roi_local_measurement_line(angle_deg: float) -> None:
    roi = RotatedRoi(center_x=130.0, center_y=110.0, width=130.0, height=80.0, angle_deg=angle_deg)
    result = BalloonEnvelopeDetector().detect(
        frame=_single_object_frame(roi),
        roi=roi,
        segmentation=_segmentation(),
        params=BalloonEnvelopeDetectorParams(boundary_margin_px=4.0),
    )

    assert result.status is DetectionStatus.OK
    assert result.point_a is not None
    assert result.point_b is not None
    _assert_same_local_measurement_line(roi, result.point_a, result.point_b, result.diagnostics)
    assert result.diagnostics.pattern_model == "blank_object_blank"
    assert result.diagnostics.detected_pattern == "blank_object_blank"
    assert result.diagnostics.object_interval_count == 1


def test_balloon_does_not_use_projection_extrema_as_formal_ab() -> None:
    roi = RotatedRoi(center_x=130.0, center_y=110.0, width=130.0, height=90.0, angle_deg=0.0)
    result = BalloonEnvelopeDetector().detect(
        frame=_skewed_single_object_frame(roi),
        roi=roi,
        segmentation=_segmentation(),
        params=BalloonEnvelopeDetectorParams(boundary_margin_px=4.0),
    )

    assert result.status is DetectionStatus.OK
    assert result.point_a is not None
    assert result.point_b is not None
    a_local = _acquisition_to_local(roi, result.point_a)
    b_local = _acquisition_to_local(roi, result.point_b)
    assert abs(a_local[1] - b_local[1]) <= 1.0
    assert result.diagnostics.local_y_delta_px is not None
    assert result.diagnostics.local_y_delta_px <= 1.0


def test_open_mesh_mesh_outer_span_uses_outer_boundaries_of_valid_mesh_intervals() -> None:
    roi = RotatedRoi(center_x=130.0, center_y=110.0, width=160.0, height=80.0, angle_deg=0.0)
    result = BalloonEnvelopeDetector().detect(
        frame=_open_mesh_frame(roi),
        roi=roi,
        segmentation=_segmentation(),
        params=BalloonEnvelopeDetectorParams(envelope_mode="open_mesh", boundary_margin_px=4.0),
    )

    assert result.status is DetectionStatus.OK
    assert result.point_a is not None
    assert result.point_b is not None
    _assert_same_local_measurement_line(roi, result.point_a, result.point_b, result.diagnostics)
    a_local = _acquisition_to_local(roi, result.point_a)
    b_local = _acquisition_to_local(roi, result.point_b)
    assert a_local[0] == pytest.approx(-56.0, abs=1.0)
    assert b_local[0] == pytest.approx(56.0, abs=1.0)
    assert result.diagnostics.detected_pattern == "mesh_outer_span"
    assert result.diagnostics.object_interval_count == 4
    assert result.diagnostics.selected_valid_intervals is not None
    assert len(result.diagnostics.selected_valid_intervals) == 4
    assert result.diagnostics.leftmost_valid_interval is not None
    assert result.diagnostics.rightmost_valid_interval is not None
    assert result.diagnostics.formal_point_a_source_interval is not None
    assert result.diagnostics.formal_point_b_source_interval is not None
    assert result.diagnostics.point_a_on_foreground_boundary is True
    assert result.diagnostics.point_b_on_foreground_boundary is True
    assert result.diagnostics.point_a_source_layer == "bridged_foreground"
    assert result.diagnostics.point_b_source_layer == "bridged_foreground"
    assert result.diagnostics.internal_gap_count == 3
    assert result.diagnostics.max_internal_gap_px is not None
    assert result.diagnostics.max_internal_gap_px > 20.0
    assert result.diagnostics.mesh_outer_span_px == pytest.approx(
        result.diagnostics.formal_ab_span_px
    )
    assert result.diagnostics.virtual_envelope_span_px is not None
    assert result.diagnostics.point_a_source_layer != "filled_envelope"
    assert result.diagnostics.point_b_source_layer != "filled_envelope"
    assert result.diagnostics.candidate_line_is_debug_only is False


def test_open_mesh_does_not_use_filled_envelope_as_formal_contact_source() -> None:
    roi = RotatedRoi(center_x=130.0, center_y=110.0, width=160.0, height=80.0, angle_deg=0.0)
    result = BalloonEnvelopeDetector().detect(
        frame=_open_mesh_frame(roi),
        roi=roi,
        segmentation=_segmentation(),
        params=BalloonEnvelopeDetectorParams(
            envelope_mode="open_mesh",
            contact_source="filled_envelope",
            boundary_margin_px=4.0,
        ),
    )

    assert result.valid is False
    assert result.point_a is None
    assert result.point_b is None
    assert result.distance_px is None
    assert result.diagnostics.envelope_mode == "open_mesh"
    assert result.diagnostics.contact_source_used == "filled_envelope"
    assert result.diagnostics.point_a_source_layer != "filled_envelope"
    assert result.diagnostics.point_b_source_layer != "filled_envelope"
    assert result.diagnostics.candidate_line_is_debug_only is True


def test_open_mesh_rejects_when_outer_span_right_edge_exists_only_in_debug_envelope() -> None:
    roi = RotatedRoi(center_x=130.0, center_y=110.0, width=160.0, height=80.0, angle_deg=0.0)
    result = BalloonEnvelopeDetector().detect(
        frame=_open_mesh_with_right_debug_only_fill_frame(roi),
        roi=roi,
        segmentation=_segmentation(),
        params=BalloonEnvelopeDetectorParams(envelope_mode="open_mesh", boundary_margin_px=4.0),
    )

    assert result.valid is False
    assert result.point_a is None
    assert result.point_b is None
    assert result.distance_px is None
    assert result.diagnostics.rejected_candidate_point_a is not None
    assert result.diagnostics.rejected_candidate_point_b is not None
    assert result.diagnostics.point_b_on_foreground_boundary is not True
    assert result.diagnostics.candidate_line_is_debug_only is True


@pytest.mark.parametrize("angle_deg", [0.0, 90.0, 30.0])
def test_wire_strip_bundle_envelope_uses_bundle_outer_span_on_same_line(angle_deg: float) -> None:
    roi = RotatedRoi(center_x=130.0, center_y=110.0, width=140.0, height=80.0, angle_deg=angle_deg)
    result = WireStripDetector().detect(
        frame=_open_mesh_frame(roi),
        roi=roi,
        segmentation=_segmentation(),
        params=WireStripDetectorParams(boundary_margin_px=3.0),
    )

    assert result.status is DetectionStatus.OK
    assert result.point_a is not None
    assert result.point_b is not None
    _assert_same_local_measurement_line(roi, result.point_a, result.point_b, result.diagnostics)
    assert result.diagnostics.pattern_model == "blank_wire_bundle_envelope_blank"
    assert result.diagnostics.detected_pattern == "wire_bundle_envelope"
    assert result.diagnostics.object_interval_count == 4
    assert result.diagnostics.interval_count == 4
    assert result.diagnostics.measurement_mode == "wire_bundle_envelope"
    assert result.diagnostics.selected_valid_intervals is not None
    assert len(result.diagnostics.selected_valid_intervals) == 4
    assert result.diagnostics.bundle_outer_span_px == pytest.approx(
        result.diagnostics.formal_ab_span_px
    )


def test_wire_strip_rejects_single_interval_as_insufficient_bundle_support() -> None:
    roi = RotatedRoi(center_x=130.0, center_y=110.0, width=140.0, height=80.0, angle_deg=0.0)
    result = WireStripDetector().detect(
        frame=_single_object_frame(roi),
        roi=roi,
        segmentation=_segmentation(),
        params=WireStripDetectorParams(boundary_margin_px=3.0),
    )

    assert result.valid is False
    assert result.point_a is None
    assert result.point_b is None
    assert result.distance_px is None
    assert result.diagnostics.pattern_model == "blank_wire_bundle_envelope_blank"
    assert result.diagnostics.detected_pattern != "wire_bundle_envelope"
