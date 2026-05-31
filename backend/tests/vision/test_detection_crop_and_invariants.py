"""Crop-offset A/B mapping regression + formal A/B invariant guard.

These tests pin the two root causes the fix addresses:

1. ``extract_roi_crop`` runs detection in a crop-local window. Every
   acquisition-space output must be shifted back to true acquisition
   coordinates, so formal A/B always lands inside the ROI and frame and matches
   the equivalent un-cropped detection (ROI-local + distance are invariant).
2. The morphology backend (SciPy vs NumPy fallback) must not change formal A/B,
   status, or distance.
"""

from __future__ import annotations

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
from yyt1771_af.vision import morphology
from yyt1771_af.vision.balloon_envelope_detector import BalloonEnvelopeDetector
from yyt1771_af.vision.roi_ops import acquisition_to_roi_local_point, assert_ab_invariants
from yyt1771_af.vision.wire_strip_detector import WireStripDetector

# A large frame (>= 400k px with a small ROI) forces ``extract_roi_crop`` to crop.
_BIG_HEIGHT = 2048
_BIG_WIDTH = 1364


def _ellipse_frame(width=240, height=180, center=(120.0, 90.0), radii=(60.0, 30.0)) -> np.ndarray:
    y, x = np.indices((height, width))
    cx, cy = center
    rx, ry = radii
    image = np.full((height, width), 230, dtype=np.uint8)
    image[((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0] = 30
    return image


def _wire_bundle_frame(roi: RotatedRoi, width=240, height=180) -> np.ndarray:
    y, x = np.indices((height, width))
    angle = math.radians(roi.angle_deg)
    unit_x = (math.cos(angle), math.sin(angle))
    unit_y = (-unit_x[1], unit_x[0])
    dx = x.astype(float) - roi.center_x
    dy = y.astype(float) - roi.center_y
    local_x = dx * unit_x[0] + dy * unit_x[1]
    local_y = dx * unit_y[0] + dy * unit_y[1]
    intervals = ((-48.0, -42.0), (-14.0, -8.0), (38.0, 46.0))
    interval_masks = [(local_x >= start) & (local_x <= end) for start, end in intervals]
    mask = np.logical_or.reduce(interval_masks) & (np.abs(local_y) <= 24.0)
    image = np.full((height, width), 230, dtype=np.uint8)
    image[mask] = 30
    return image


def _embed(small: np.ndarray, *, top: int, left: int, background: int = 230) -> np.ndarray:
    big = np.full((_BIG_HEIGHT, _BIG_WIDTH), background, dtype=np.uint8)
    big[top : top + small.shape[0], left : left + small.shape[1]] = small
    return big


def _local(point: Point2D, roi: RotatedRoi) -> tuple[float, float]:
    local = acquisition_to_roi_local_point(roi, point)
    return local.x, local.y


def _balloon_segmentation() -> SegmentationParams:
    return SegmentationParams(close_kernel=7, open_kernel=1)


def _wire_segmentation() -> SegmentationParams:
    return SegmentationParams(
        polarity="dark_on_light",
        threshold_mode="fixed",
        threshold_value=160,
        close_kernel=1,
        open_kernel=1,
        min_component_area_px=20,
    )


def test_balloon_crop_offset_keeps_ab_inside_roi_and_matches_uncropped() -> None:
    detector = BalloonEnvelopeDetector()
    small_frame = _ellipse_frame()
    small_roi = RotatedRoi(center_x=120.0, center_y=90.0, width=150.0, height=90.0, angle_deg=0.0)

    top, left = 520, 880
    big_frame = _embed(small_frame, top=top, left=left)
    big_roi = small_roi.model_copy(
        update={"center_x": small_roi.center_x + left, "center_y": small_roi.center_y + top}
    )

    reference = detector.detect(
        frame=small_frame,
        roi=small_roi,
        segmentation=_balloon_segmentation(),
        params=BalloonEnvelopeDetectorParams(),
    )
    cropped = detector.detect(
        frame=big_frame,
        roi=big_roi,
        segmentation=_balloon_segmentation(),
        params=BalloonEnvelopeDetectorParams(),
    )

    assert reference.status is DetectionStatus.OK and reference.valid is True
    assert cropped.status is DetectionStatus.OK and cropped.valid is True
    # Formal A/B must be acquisition-space, inside the frame, and inside the ROI.
    for point in (cropped.point_a, cropped.point_b):
        assert point.coordinate_space is CoordinateSpace.ACQUISITION
        assert 0 <= point.x < _BIG_WIDTH and 0 <= point.y < _BIG_HEIGHT
        local_x, local_y = _local(point, big_roi)
        assert abs(local_x) <= big_roi.width / 2.0 + 1.0
        assert abs(local_y) <= big_roi.height / 2.0 + 1.0
    # ROI-local A/B and distance are translation-invariant: cropped == reference.
    assert _local(cropped.point_a, big_roi) == pytest.approx(
        _local(reference.point_a, small_roi), abs=0.5
    )
    assert _local(cropped.point_b, big_roi) == pytest.approx(
        _local(reference.point_b, small_roi), abs=0.5
    )
    assert cropped.distance_px == pytest.approx(reference.distance_px, abs=0.5)


def test_wire_crop_offset_keeps_ab_inside_roi_and_matches_uncropped() -> None:
    detector = WireStripDetector()
    small_roi = RotatedRoi(center_x=120.0, center_y=90.0, width=130.0, height=90.0, angle_deg=0.0)
    small_frame = _wire_bundle_frame(small_roi)

    top, left = 540, 900
    big_frame = _embed(small_frame, top=top, left=left)
    big_roi = small_roi.model_copy(
        update={"center_x": small_roi.center_x + left, "center_y": small_roi.center_y + top}
    )

    reference = detector.detect(
        frame=small_frame,
        roi=small_roi,
        segmentation=_wire_segmentation(),
        params=WireStripDetectorParams(),
    )
    cropped = detector.detect(
        frame=big_frame,
        roi=big_roi,
        segmentation=_wire_segmentation(),
        params=WireStripDetectorParams(),
    )

    assert reference.status is DetectionStatus.OK and reference.valid is True
    assert cropped.status is DetectionStatus.OK and cropped.valid is True
    for point in (cropped.point_a, cropped.point_b):
        assert point.coordinate_space is CoordinateSpace.ACQUISITION
        assert 0 <= point.x < _BIG_WIDTH and 0 <= point.y < _BIG_HEIGHT
        local_x, local_y = _local(point, big_roi)
        assert abs(local_x) <= big_roi.width / 2.0 + 1.0
        assert abs(local_y) <= big_roi.height / 2.0 + 1.0
    assert _local(cropped.point_a, big_roi) == pytest.approx(
        _local(reference.point_a, small_roi), abs=0.5
    )
    assert _local(cropped.point_b, big_roi) == pytest.approx(
        _local(reference.point_b, small_roi), abs=0.5
    )
    assert cropped.distance_px == pytest.approx(reference.distance_px, abs=0.5)


def test_balloon_detection_identical_with_numpy_fallback(monkeypatch) -> None:
    detector = BalloonEnvelopeDetector()
    frame = _ellipse_frame()
    roi = RotatedRoi(center_x=120.0, center_y=90.0, width=150.0, height=90.0, angle_deg=0.0)
    scipy_result = detector.detect(
        frame=frame,
        roi=roi,
        segmentation=_balloon_segmentation(),
        params=BalloonEnvelopeDetectorParams(),
    )
    monkeypatch.setattr(morphology, "_ndimage", None)
    numpy_result = detector.detect(
        frame=frame,
        roi=roi,
        segmentation=_balloon_segmentation(),
        params=BalloonEnvelopeDetectorParams(),
    )
    _assert_same_formal_result(scipy_result, numpy_result)


def test_wire_detection_identical_with_numpy_fallback(monkeypatch) -> None:
    detector = WireStripDetector()
    roi = RotatedRoi(center_x=120.0, center_y=90.0, width=130.0, height=90.0, angle_deg=0.0)
    frame = _wire_bundle_frame(roi)
    scipy_result = detector.detect(
        frame=frame, roi=roi, segmentation=_wire_segmentation(), params=WireStripDetectorParams()
    )
    monkeypatch.setattr(morphology, "_ndimage", None)
    numpy_result = detector.detect(
        frame=frame, roi=roi, segmentation=_wire_segmentation(), params=WireStripDetectorParams()
    )
    _assert_same_formal_result(scipy_result, numpy_result)


def test_assert_ab_invariants_accepts_valid_points() -> None:
    roi = RotatedRoi(center_x=50.0, center_y=50.0, width=40.0, height=40.0, angle_deg=0.0)
    mask = np.zeros((100, 100), dtype=bool)
    mask[40:61, 30:71] = True
    point_a = Point2D(x=30.0, y=50.0, coordinate_space=CoordinateSpace.ACQUISITION)
    point_b = Point2D(x=70.0, y=50.0, coordinate_space=CoordinateSpace.ACQUISITION)
    assert (
        assert_ab_invariants(
            point_a, point_b, roi=roi, frame_shape=mask.shape, foreground_mask=mask
        )
        is None
    )


def test_assert_ab_invariants_rejects_point_outside_roi() -> None:
    roi = RotatedRoi(center_x=50.0, center_y=50.0, width=40.0, height=40.0, angle_deg=0.0)
    mask = np.ones((100, 100), dtype=bool)
    point_a = Point2D(x=5.0, y=50.0, coordinate_space=CoordinateSpace.ACQUISITION)
    point_b = Point2D(x=70.0, y=50.0, coordinate_space=CoordinateSpace.ACQUISITION)
    reason = assert_ab_invariants(
        point_a, point_b, roi=roi, frame_shape=mask.shape, foreground_mask=mask
    )
    assert reason == "point_a_outside_roi"


def test_assert_ab_invariants_rejects_point_off_foreground() -> None:
    roi = RotatedRoi(center_x=50.0, center_y=50.0, width=40.0, height=40.0, angle_deg=0.0)
    mask = np.zeros((100, 100), dtype=bool)
    mask[40:61, 45:56] = True
    point_a = Point2D(x=35.0, y=50.0, coordinate_space=CoordinateSpace.ACQUISITION)
    point_b = Point2D(x=50.0, y=50.0, coordinate_space=CoordinateSpace.ACQUISITION)
    reason = assert_ab_invariants(
        point_a, point_b, roi=roi, frame_shape=mask.shape, foreground_mask=mask
    )
    assert reason == "point_a_off_foreground"


def test_assert_ab_invariants_rejects_point_outside_frame() -> None:
    roi = RotatedRoi(center_x=50.0, center_y=50.0, width=400.0, height=400.0, angle_deg=0.0)
    mask = np.ones((100, 100), dtype=bool)
    point_a = Point2D(x=-10.0, y=50.0, coordinate_space=CoordinateSpace.ACQUISITION)
    point_b = Point2D(x=50.0, y=50.0, coordinate_space=CoordinateSpace.ACQUISITION)
    reason = assert_ab_invariants(
        point_a, point_b, roi=roi, frame_shape=mask.shape, foreground_mask=mask
    )
    assert reason == "point_a_outside_frame"


def _assert_same_formal_result(left, right) -> None:
    assert left.status is right.status
    assert left.valid == right.valid
    assert (left.distance_px is None) == (right.distance_px is None)
    if left.distance_px is not None:
        assert left.distance_px == pytest.approx(right.distance_px, abs=1e-6)
    for left_point, right_point in ((left.point_a, right.point_a), (left.point_b, right.point_b)):
        assert (left_point is None) == (right_point is None)
        if left_point is not None:
            assert left_point.x == pytest.approx(right_point.x, abs=1e-6)
            assert left_point.y == pytest.approx(right_point.y, abs=1e-6)
