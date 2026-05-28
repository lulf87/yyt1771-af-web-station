import numpy as np
from yyt1771_af.core.models import BalloonEnvelopeDetectorParams, RotatedRoi, SegmentationParams
from yyt1771_af.core.statuses import CoordinateSpace, DetectionStatus
from yyt1771_af.vision import segmentation as segmentation_module
from yyt1771_af.vision.balloon_envelope_detector import BalloonEnvelopeDetector
from yyt1771_af.vision.roi_ops import rotated_roi_mask


def _mesh_frame_with_bright_center() -> np.ndarray:
    image = np.full((120, 160), 230, dtype=np.uint8)
    image[30:91:12, 35:126] = 30
    image[30:91, 35:126:12] = 30
    image[56:65, 76:85] = 230
    return image


def _ellipse_frame() -> np.ndarray:
    y, x = np.indices((120, 160))
    image = np.full((120, 160), 230, dtype=np.uint8)
    image[((x - 80.0) / 44.0) ** 2 + ((y - 60.0) / 24.0) ** 2 <= 1.0] = 30
    return image


def test_auto_polarity_records_center_on_light_background_selection() -> None:
    frame = _mesh_frame_with_bright_center()
    roi = RotatedRoi(center_x=80.0, center_y=60.0, width=120.0, height=82.0, angle_deg=0.0)
    roi_mask = rotated_roi_mask(frame.shape, roi)

    _, _, debug = segmentation_module.segment_target_mask_debug(
        frame,
        roi_mask,
        SegmentationParams(polarity="auto", close_kernel=1, open_kernel=1),
        preferred_point_xy=(roi.center_x, roi.center_y),
    )

    assert debug.threshold_value is not None
    assert debug.selected_polarity == "auto_light_selected"
    assert debug.selected_reason == "preferred_point_light"
    assert debug.preferred_point_hit_dark is False
    assert debug.preferred_point_hit_light is True
    assert debug.light_area_ratio > debug.dark_area_ratio


def test_forced_dark_polarity_changes_selected_foreground() -> None:
    frame = _mesh_frame_with_bright_center()
    roi = RotatedRoi(center_x=80.0, center_y=60.0, width=120.0, height=82.0, angle_deg=0.0)
    roi_mask = rotated_roi_mask(frame.shape, roi)

    auto_foreground, _, auto_debug = segmentation_module.segment_target_mask_debug(
        frame,
        roi_mask,
        SegmentationParams(polarity="auto", close_kernel=1, open_kernel=1),
        preferred_point_xy=(roi.center_x, roi.center_y),
    )
    dark_foreground, _, dark_debug = segmentation_module.segment_target_mask_debug(
        frame,
        roi_mask,
        SegmentationParams(polarity="dark_on_light", close_kernel=1, open_kernel=1),
        preferred_point_xy=(roi.center_x, roi.center_y),
    )

    assert auto_debug.selected_polarity == "auto_light_selected"
    assert dark_debug.selected_polarity == "dark_on_light"
    assert dark_debug.selected_reason == "forced_dark"
    assert np.count_nonzero(dark_foreground) < np.count_nonzero(auto_foreground)


def test_boundary_rejection_keeps_formal_points_empty_but_records_debug_candidates() -> None:
    result = BalloonEnvelopeDetector().detect(
        frame=_ellipse_frame(),
        roi=RotatedRoi(center_x=80.0, center_y=60.0, width=72.0, height=60.0, angle_deg=0.0),
        segmentation=SegmentationParams(polarity="dark_on_light", close_kernel=5, open_kernel=1),
        params=BalloonEnvelopeDetectorParams(boundary_margin_px=4.0),
    )

    assert result.status is DetectionStatus.CALIPER_CONTACT_ON_ROI_BOUNDARY
    assert result.valid is False
    assert result.point_a is None
    assert result.point_b is None
    assert result.distance_px is None

    diagnostics = result.diagnostics
    assert diagnostics.rejected_contact_side == "both"
    assert diagnostics.distance_to_left_roi_boundary_px is not None
    assert diagnostics.distance_to_right_roi_boundary_px is not None
    assert diagnostics.distance_to_left_roi_boundary_px <= diagnostics.boundary_margin_px
    assert diagnostics.distance_to_right_roi_boundary_px <= diagnostics.boundary_margin_px
    assert diagnostics.rejected_candidate_point_a is not None
    assert diagnostics.rejected_candidate_point_b is not None
    assert diagnostics.rejected_candidate_point_a.coordinate_space is CoordinateSpace.ACQUISITION
    assert diagnostics.rejected_candidate_point_b.coordinate_space is CoordinateSpace.ACQUISITION
