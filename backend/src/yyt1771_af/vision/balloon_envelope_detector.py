from __future__ import annotations

import numpy as np

from yyt1771_af.core.models import (
    BalloonEnvelopeDetectorParams,
    DetectionDiagnostics,
    DetectionResult,
    RotatedRoi,
    SegmentationParams,
)
from yyt1771_af.core.statuses import DetectionStatus, DetectorKind, TargetFamily
from yyt1771_af.vision.roi_ops import (
    ContactRejection,
    component_bbox,
    component_roi_margins,
    failure_result,
    roi_is_inside_frame,
    rotated_roi_mask,
    select_contact_points_debug,
    valid_result,
)
from yyt1771_af.vision.segmentation import (
    connected_components,
    fill_internal_holes,
    segment_target_mask_layers_debug,
)


class BalloonEnvelopeDetector:
    detector_kind = DetectorKind.BALLOON_ENVELOPE_DETECTOR
    target_family = TargetFamily.BALLOON_ENVELOPE

    def detect(
        self,
        *,
        frame: np.ndarray,
        roi: RotatedRoi,
        segmentation: SegmentationParams | None = None,
        params: BalloonEnvelopeDetectorParams | None = None,
    ) -> DetectionResult:
        segmentation = segmentation or SegmentationParams()
        params = params or BalloonEnvelopeDetectorParams()

        if frame.ndim != 2:
            return self._failure(
                DetectionStatus.SEGMENTATION_FAILED,
                message="Frame is not grayscale.",
            )
        if not roi_is_inside_frame(frame, roi):
            return self._failure(
                DetectionStatus.ROI_OUTSIDE_FRAME,
                message="ROI is outside frame.",
            )

        roi_mask = rotated_roi_mask(frame.shape, roi)
        roi_area = max(1, int(np.count_nonzero(roi_mask)))
        segmentation_layers, contrast_quality, segmentation_debug = (
            segment_target_mask_layers_debug(
                frame,
                roi_mask,
                segmentation,
                preferred_point_xy=(roi.center_x, roi.center_y),
            )
        )
        filled_envelope = fill_internal_holes(segmentation_layers.morphology_foreground) & roi_mask
        fill_internal_holes_used = (
            params.fill_internal_holes
            if segmentation.fill_internal_holes is None
            else segmentation.fill_internal_holes
        )
        contact_source_used = (
            "filled_envelope" if fill_internal_holes_used else "morphology_foreground"
        )
        foreground = (
            filled_envelope
            if fill_internal_holes_used
            else segmentation_layers.morphology_foreground
        )
        layer_diagnostics = _segmentation_diagnostics(
            segmentation_debug,
            filled_envelope=filled_envelope,
            roi_area=roi_area,
            fill_internal_holes_used=fill_internal_holes_used,
            contact_source_used=contact_source_used,
        )
        if not np.any(foreground):
            return self._failure(
                DetectionStatus.LOW_CONTRAST,
                quality=contrast_quality,
                diagnostics_extra=layer_diagnostics,
            )

        components = connected_components(foreground, segmentation.min_component_area_px)
        if not components:
            return self._failure(
                DetectionStatus.TARGET_NOT_FOUND,
                quality=contrast_quality,
                diagnostics_extra=layer_diagnostics | {"candidate_component_count": 0},
            )
        if len(components) > 1 and components[1].area_px > components[0].area_px * 0.35:
            return self._failure(
                DetectionStatus.MULTIPLE_TARGETS,
                quality=contrast_quality,
                candidate_components=len(components),
                diagnostics_extra=layer_diagnostics
                | _component_margin_diagnostics(components[0], roi)
                | {
                    "candidate_component_count": len(components),
                    "selected_component_area_px": components[0].area_px,
                    "selected_component_bbox": component_bbox(components[0]),
                },
            )

        component = components[0]
        selection = select_contact_points_debug(
            component,
            roi,
            boundary_margin_px=params.boundary_margin_px,
            reject_contact_on_roi_boundary=params.reject_contact_on_roi_boundary,
        )
        component_diagnostics = (
            layer_diagnostics
            | _component_margin_diagnostics(component, roi)
            | {
                "candidate_component_count": len(components),
                "selected_component_area_px": component.area_px,
                "selected_component_bbox": component_bbox(component),
                "boundary_margin_px": params.boundary_margin_px,
                "roi_half_width": roi.width / 2.0,
            }
        )
        if isinstance(selection, ContactRejection):
            return self._failure(
                selection.status,
                quality=contrast_quality,
                contour_area_px=float(component.area_px),
                contour_point_count=selection.debug.contour_point_count,
                candidate_components=len(components),
                diagnostics_extra=component_diagnostics
                | _contact_diagnostics(selection.debug)
                | {
                    "message": _failure_message(selection.status, selection.debug.rejected_side),
                },
            )

        quality = max(params.min_quality, min(0.98, 0.65 + 0.3 * contrast_quality))
        result = valid_result(
            target_family=self.target_family,
            detector=self.detector_kind,
            selection=selection,
            contour_area_px=float(component.area_px),
            candidate_components=len(components),
            quality=quality,
        )
        result.diagnostics = DetectionDiagnostics.model_validate(
            result.diagnostics.model_dump(mode="python")
            | component_diagnostics
            | {
                "contour_point_count": selection.contour_point_count,
                "min_local_projection": selection.min_local_projection,
                "max_local_projection": selection.max_local_projection,
                "distance_to_left_roi_boundary_px": selection.distance_to_left_roi_boundary_px,
                "distance_to_right_roi_boundary_px": selection.distance_to_right_roi_boundary_px,
            }
        )
        return result

    def _failure(
        self,
        status: DetectionStatus,
        *,
        quality: float = 0.0,
        contour_area_px: float | None = None,
        contour_point_count: int | None = None,
        candidate_components: int | None = None,
        message: str | None = None,
        diagnostics_extra: dict[str, object] | None = None,
    ) -> DetectionResult:
        return failure_result(
            target_family=self.target_family,
            detector=self.detector_kind,
            status=status,
            quality=quality,
            contour_area_px=contour_area_px,
            contour_point_count=contour_point_count,
            candidate_components=candidate_components,
            message=message,
            diagnostics_extra=diagnostics_extra,
        )


def _segmentation_diagnostics(
    segmentation_debug: object,
    *,
    filled_envelope: np.ndarray,
    roi_area: int,
    fill_internal_holes_used: bool,
    contact_source_used: str,
) -> dict[str, object]:
    filled_area = int(np.count_nonzero(filled_envelope))
    return {
        "threshold_value": segmentation_debug.threshold_value,
        "selected_polarity": segmentation_debug.selected_polarity,
        "selected_reason": segmentation_debug.selected_reason,
        "contrast": segmentation_debug.contrast,
        "dark_area_ratio": segmentation_debug.dark_area_ratio,
        "light_area_ratio": segmentation_debug.light_area_ratio,
        "preferred_point_xy": {
            "x": segmentation_debug.preferred_point_xy[0],
            "y": segmentation_debug.preferred_point_xy[1],
        }
        if segmentation_debug.preferred_point_xy is not None
        else None,
        "preferred_point_hit_dark": segmentation_debug.preferred_point_hit_dark,
        "preferred_point_hit_light": segmentation_debug.preferred_point_hit_light,
        "raw_foreground_area_px": segmentation_debug.raw_foreground_area_px,
        "raw_foreground_ratio": segmentation_debug.raw_foreground_ratio,
        "morphology_foreground_area_px": segmentation_debug.morphology_foreground_area_px,
        "morphology_foreground_ratio": segmentation_debug.morphology_foreground_ratio,
        "filled_envelope_area_px": filled_area,
        "filled_envelope_ratio": float(filled_area / max(1, roi_area)),
        "foreground_area_px": segmentation_debug.foreground_area_px,
        "foreground_area_ratio_in_roi": segmentation_debug.foreground_area_ratio_in_roi,
        "fill_internal_holes_used": fill_internal_holes_used,
        "contact_source_used": contact_source_used,
    }


def _contact_diagnostics(contact_debug: object) -> dict[str, object]:
    return {
        "contour_point_count": contact_debug.contour_point_count,
        "min_local_projection": contact_debug.min_local_projection,
        "max_local_projection": contact_debug.max_local_projection,
        "distance_to_left_roi_boundary_px": contact_debug.distance_to_left_roi_boundary_px,
        "distance_to_right_roi_boundary_px": contact_debug.distance_to_right_roi_boundary_px,
        "rejected_contact_side": contact_debug.rejected_side,
        "rejected_candidate_point_a": contact_debug.rejected_candidate_point_a,
        "rejected_candidate_point_b": contact_debug.rejected_candidate_point_b,
    }


def _component_margin_diagnostics(component: object, roi: RotatedRoi) -> dict[str, object]:
    margins = component_roi_margins(component, roi)
    return {
        "left_margin_px": margins.left_margin_px,
        "right_margin_px": margins.right_margin_px,
        "top_margin_px": margins.top_margin_px,
        "bottom_margin_px": margins.bottom_margin_px,
    }


def _failure_message(status: DetectionStatus, rejected_side: str | None) -> str | None:
    if status is DetectionStatus.CALIPER_CONTACT_ON_ROI_BOUNDARY:
        side_text = rejected_side or "unknown"
        return f"Detected contour contact is too close to the {side_text} ROI measurement boundary."
    return None
