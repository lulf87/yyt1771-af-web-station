import numpy as np
from yyt1771_af.core.models import RotatedRoi, SegmentationParams
from yyt1771_af.vision.wire_auto_tune import auto_tune_wire_threshold


def _clean_wire_bundle() -> tuple[np.ndarray, RotatedRoi]:
    roi = RotatedRoi(center_x=120.0, center_y=90.0, width=130.0, height=90.0, angle_deg=0.0)
    y, x = np.indices((180, 240))
    dx = x.astype(float) - roi.center_x
    dy = y.astype(float) - roi.center_y
    wires = (
        ((dx >= -48.0) & (dx <= -42.0))
        | ((dx >= -14.0) & (dx <= -8.0))
        | ((dx >= 38.0) & (dx <= 46.0))
    ) & (np.abs(dy) <= 24.0)
    image = np.full((180, 240), 230, dtype=np.uint8)
    image[wires] = 30
    return image, roi


def _wire_bundle_with_high_threshold_blob() -> tuple[np.ndarray, RotatedRoi]:
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
    image[blob] = 110
    image[wires] = 30
    return image, roi


def test_auto_tune_recommends_stable_platform_threshold() -> None:
    frame, roi = _clean_wire_bundle()

    result = auto_tune_wire_threshold(
        frame=frame,
        roi=roi,
        base_segmentation=SegmentationParams(polarity="dark_on_light", min_component_area_px=20),
        candidate_thresholds=[80, 100, 120, 140, 160],
    )

    assert result.auto_tuned is True
    assert result.selected_reason == "stable_platform"
    assert result.recommended_threshold_value in {80, 100, 120, 140, 160}
    assert result.stable_platform_min is not None
    assert result.stable_platform_max is not None
    assert all(candidate.valid for candidate in result.candidates)
    assert any(candidate.on_stable_platform for candidate in result.candidates)


def test_auto_tune_avoids_thresholds_that_admit_broad_blob() -> None:
    frame, roi = _wire_bundle_with_high_threshold_blob()

    result = auto_tune_wire_threshold(
        frame=frame,
        roi=roi,
        base_segmentation=SegmentationParams(polarity="dark_on_light", min_component_area_px=20),
        candidate_thresholds=[80, 90, 100, 115, 125, 135],
    )

    assert result.auto_tuned is True
    assert result.recommended_threshold_value is not None
    # The broad blob (value 110) only enters the foreground at higher thresholds.
    assert result.recommended_threshold_value < 110
    by_threshold = {c.threshold_value: c for c in result.candidates}
    assert by_threshold[125].broad_blob_rejection_count is not None
    assert by_threshold[125].broad_blob_rejection_count >= 1
    assert by_threshold[125].on_stable_platform is False


def test_auto_tune_candidates_expose_wire_filtering_evidence() -> None:
    frame, roi = _wire_bundle_with_high_threshold_blob()

    result = auto_tune_wire_threshold(
        frame=frame,
        roi=roi,
        base_segmentation=SegmentationParams(polarity="dark_on_light", min_component_area_px=20),
        candidate_thresholds=[80, 125],
    )

    by_threshold = {candidate.threshold_value: candidate for candidate in result.candidates}
    accepted = by_threshold[80]
    rejected_blob = by_threshold[125]

    assert accepted.selected_valid_intervals
    assert accepted.point_a_on_foreground_boundary is True
    assert accepted.point_b_on_foreground_boundary is True
    assert accepted.local_contrast_score is not None
    assert accepted.neighbor_line_support is not None
    assert accepted.failure_reason is None

    assert rejected_blob.broad_blob_area_ratio is not None
    assert rejected_blob.rejected_interval_count >= 1
    assert rejected_blob.failure_reason is None
