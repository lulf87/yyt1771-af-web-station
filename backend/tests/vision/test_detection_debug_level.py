"""``debug_level`` controls diagnostic cost without changing formal A/B.

``basic`` (Live Offline Run playback) must skip the heavy diagnostic passes
(wire rejected intervals + the lazily attached raw/bridged/virtual-envelope
intervals) while producing exactly the same ``status``, ``point_a``/``point_b``
and ``distance_px`` as ``full`` (Setup / single-frame inspection).
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from yyt1771_af.core.models import (
    BalloonEnvelopeDetectorParams,
    RotatedRoi,
    SegmentationParams,
    WireStripDetectorParams,
)
from yyt1771_af.core.statuses import DetectionStatus
from yyt1771_af.vision.balloon_envelope_detector import BalloonEnvelopeDetector
from yyt1771_af.vision.wire_strip_detector import WireStripDetector


def _wire_bundle_frame(roi: RotatedRoi) -> np.ndarray:
    y, x = np.indices((180, 240))
    angle = math.radians(roi.angle_deg)
    unit_x = (math.cos(angle), math.sin(angle))
    unit_y = (-unit_x[1], unit_x[0])
    dx = x.astype(float) - roi.center_x
    dy = y.astype(float) - roi.center_y
    local_x = dx * unit_x[0] + dy * unit_x[1]
    local_y = dx * unit_y[0] + dy * unit_y[1]
    intervals = ((-48.0, -42.0), (-14.0, -8.0), (38.0, 46.0))
    mask = np.logical_or.reduce(
        [(local_x >= start) & (local_x <= end) for start, end in intervals]
    ) & (np.abs(local_y) <= 24.0)
    image = np.full((180, 240), 230, dtype=np.uint8)
    image[mask] = 30
    return image


def _wire_bundle_with_blob_frame() -> tuple[np.ndarray, RotatedRoi]:
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


def _ellipse_frame() -> np.ndarray:
    y, x = np.indices((180, 240))
    image = np.full((180, 240), 230, dtype=np.uint8)
    image[((x - 120.0) / 60.0) ** 2 + ((y - 90.0) / 30.0) ** 2 <= 1.0] = 30
    return image


def _wire_segmentation() -> SegmentationParams:
    return SegmentationParams(
        polarity="dark_on_light",
        threshold_mode="fixed",
        threshold_value=160,
        close_kernel=1,
        open_kernel=1,
        min_component_area_px=20,
    )


def _assert_same_formal_result(full, basic) -> None:
    assert full.status is basic.status
    assert full.valid == basic.valid
    assert full.distance_px == pytest.approx(basic.distance_px)
    assert full.point_a.x == pytest.approx(basic.point_a.x)
    assert full.point_a.y == pytest.approx(basic.point_a.y)
    assert full.point_b.x == pytest.approx(basic.point_b.x)
    assert full.point_b.y == pytest.approx(basic.point_b.y)


def test_wire_basic_matches_full_formal_ab_but_skips_heavy_diagnostics() -> None:
    detector = WireStripDetector()
    roi = RotatedRoi(center_x=120.0, center_y=90.0, width=130.0, height=90.0, angle_deg=0.0)
    frame = _wire_bundle_frame(roi)

    full = detector.detect(
        frame=frame,
        roi=roi,
        segmentation=_wire_segmentation(),
        params=WireStripDetectorParams(),
        debug_level="full",
    )
    basic = detector.detect(
        frame=frame,
        roi=roi,
        segmentation=_wire_segmentation(),
        params=WireStripDetectorParams(),
        debug_level="basic",
    )

    assert full.status is DetectionStatus.OK
    _assert_same_formal_result(full, basic)
    # Heavy diagnostics present at full, skipped at basic.
    assert full.diagnostics.raw_intervals is not None
    assert basic.diagnostics.raw_intervals is None
    assert basic.diagnostics.bridged_intervals is None
    assert full.diagnostics.selected_valid_intervals is not None
    assert basic.diagnostics.selected_valid_intervals is None
    assert basic.diagnostics.point_a_source_interval is not None
    assert basic.diagnostics.point_b_source_interval is not None
    assert basic.diagnostics.selected_bundle_cluster_id is not None
    assert basic.diagnostics.selected_bundle_support_ratio is not None
    assert basic.diagnostics.remote_interval_rejection_count is not None


def test_wire_basic_skips_rejected_interval_diagnostics() -> None:
    detector = WireStripDetector()
    frame, roi = _wire_bundle_with_blob_frame()

    full = detector.detect(
        frame=frame,
        roi=roi,
        segmentation=_wire_segmentation(),
        params=WireStripDetectorParams(),
        debug_level="full",
    )
    basic = detector.detect(
        frame=frame,
        roi=roi,
        segmentation=_wire_segmentation(),
        params=WireStripDetectorParams(),
        debug_level="basic",
    )

    _assert_same_formal_result(full, basic)
    assert full.diagnostics.rejected_intervals is not None
    assert basic.diagnostics.rejected_intervals is None
    assert basic.diagnostics.rejected_interval_reasons is None


def test_balloon_basic_matches_full_formal_ab() -> None:
    detector = BalloonEnvelopeDetector()
    roi = RotatedRoi(center_x=120.0, center_y=90.0, width=150.0, height=90.0, angle_deg=0.0)
    frame = _ellipse_frame()
    segmentation = SegmentationParams(close_kernel=7, open_kernel=1)

    full = detector.detect(
        frame=frame,
        roi=roi,
        segmentation=segmentation,
        params=BalloonEnvelopeDetectorParams(),
        debug_level="full",
    )
    basic = detector.detect(
        frame=frame,
        roi=roi,
        segmentation=segmentation,
        params=BalloonEnvelopeDetectorParams(),
        debug_level="basic",
    )

    assert full.status is DetectionStatus.OK
    _assert_same_formal_result(full, basic)
    # The solid balloon line candidate never carries the lazily attached debug
    # intervals, so both levels agree (balloon throughput is restored by the
    # morphology backend, not by dropping debug intervals).
    assert full.diagnostics.raw_intervals is None
    assert basic.diagnostics.raw_intervals is None
