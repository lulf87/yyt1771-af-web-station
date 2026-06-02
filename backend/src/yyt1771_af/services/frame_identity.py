from __future__ import annotations

from typing import Any

from yyt1771_af.core.models import (
    BalloonEnvelopeDetectorParams,
    DetectorParams,
    Frame,
    FrameIdentity,
    RotatedRoi,
    SegmentationParams,
    WireStripDetectorParams,
)
from yyt1771_af.core.statuses import TargetFamily


def recipe_summary(
    *,
    target_family: TargetFamily,
    recipe_name: str | None,
    roi: RotatedRoi,
    segmentation: SegmentationParams,
    detector: DetectorParams,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "target_family": target_family.value,
        "recipe_name": recipe_name,
        "roi": {
            "center_x": roi.center_x,
            "center_y": roi.center_y,
            "width": roi.width,
            "height": roi.height,
            "angle_deg": roi.angle_deg,
        },
        "threshold_mode": segmentation.threshold_mode,
        "threshold_value": segmentation.threshold_value,
        "polarity": segmentation.polarity,
        "segmentation_min_component_area_px": segmentation.min_component_area_px,
        "detector_kind": detector.detector_kind.value,
        "measurement_model": detector.measurement_model,
    }
    if isinstance(detector, WireStripDetectorParams):
        payload |= {
            "measurement_mode": detector.measurement_mode,
            "max_bundle_internal_gap_px": detector.max_bundle_internal_gap_px,
            "max_bundle_internal_gap_ratio": detector.max_bundle_internal_gap_ratio,
            "detector_min_component_area_px": detector.min_component_area_px,
            "min_support_ratio": detector.min_support_ratio,
            "span_tie_tolerance_px": detector.span_tie_tolerance_px,
        }
    if isinstance(detector, BalloonEnvelopeDetectorParams):
        payload |= {
            "envelope_mode": detector.envelope_mode,
            "contact_source": detector.contact_source,
        }
    return payload


def frame_identity(
    *,
    frame: Frame,
    source_type: str,
    recipe: dict[str, Any] | None = None,
    debug_level: str | None = None,
) -> FrameIdentity:
    return FrameIdentity(
        frame_id=frame.frame_id,
        frame_index=frame.frame_index,
        frame_name=frame.frame_name,
        source_type=source_type,
        acquisition_width=frame.width,
        acquisition_height=frame.height,
        recipe_summary=recipe,
        debug_level=debug_level,
    )
