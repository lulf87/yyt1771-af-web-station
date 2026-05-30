from __future__ import annotations

import numpy as np

from yyt1771_af.core.models import (
    DetectionDiagnostics,
    DetectionResult,
    RotatedRoi,
    SegmentationParams,
    WireStripDetectorParams,
)
from yyt1771_af.core.statuses import DetectionStatus, DetectorKind, TargetFamily
from yyt1771_af.vision.roi_ops import (
    ContactRejection,
    component_bbox,
    failure_result,
    mask_bbox,
    mask_roi_margins,
    roi_is_inside_frame,
    rotated_roi_mask,
    select_roi_local_chord_contacts_debug,
    valid_result,
)
from yyt1771_af.vision.segmentation import connected_components, segment_target_mask_debug


class WireStripDetector:
    detector_kind = DetectorKind.WIRE_STRIP_DETECTOR
    target_family = TargetFamily.WIRE_STRIP

    def detect(
        self,
        *,
        frame: np.ndarray,
        roi: RotatedRoi,
        segmentation: SegmentationParams | None = None,
        params: WireStripDetectorParams | None = None,
    ) -> DetectionResult:
        segmentation = segmentation or SegmentationParams()
        params = params or WireStripDetectorParams()

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
        foreground, contrast_quality, segmentation_debug = segment_target_mask_debug(
            frame,
            roi_mask,
            segmentation,
            preferred_point_xy=(roi.center_x, roi.center_y),
        )
        if not np.any(foreground):
            return self._failure(
                DetectionStatus.LOW_CONTRAST,
                quality=contrast_quality,
                diagnostics_extra=_segmentation_diagnostics(segmentation_debug),
            )

        components = connected_components(foreground, segmentation.min_component_area_px)
        if not components:
            return self._failure(
                DetectionStatus.TARGET_NOT_FOUND,
                quality=contrast_quality,
                diagnostics_extra=_segmentation_diagnostics(segmentation_debug)
                | {"candidate_component_count": 0},
            )
        selection = select_roi_local_chord_contacts_debug(
            foreground,
            roi,
            pattern_model=params.measurement_model,
            measurement_mode=params.measurement_mode,
            boundary_margin_px=params.boundary_margin_px,
            reject_contact_on_roi_boundary=params.reject_contact_on_roi_boundary,
            allow_mesh_outer_span=True,
            source_layer="wire_foreground",
            raw_foreground_mask=foreground,
            bridged_foreground_mask=foreground,
            min_mesh_interval_count=2,
            bundle_detected_pattern="wire_bundle_envelope",
            prefer_largest_formal_span=True,
            reject_global_foreground_boundary=False,
        )
        selected_bbox = mask_bbox(foreground)
        margins = mask_roi_margins(foreground, roi)
        component_diagnostics = _segmentation_diagnostics(segmentation_debug) | {
            "candidate_component_count": len(components),
            "selected_component_area_px": int(np.count_nonzero(foreground)),
            "selected_component_bbox": selected_bbox or component_bbox(components[0]),
            "boundary_margin_px": params.boundary_margin_px,
            "roi_half_width": roi.width / 2.0,
            "pattern_model": params.measurement_model,
            "measurement_mode": params.measurement_mode,
        }
        if margins is not None:
            component_diagnostics |= {
                "left_margin_px": margins.left_margin_px,
                "right_margin_px": margins.right_margin_px,
                "top_margin_px": margins.top_margin_px,
                "bottom_margin_px": margins.bottom_margin_px,
            }
        if isinstance(selection, ContactRejection):
            return self._failure(
                selection.status,
                quality=contrast_quality,
                contour_area_px=float(np.count_nonzero(foreground)),
                contour_point_count=selection.debug.contour_point_count,
                candidate_components=len(components),
                diagnostics_extra=component_diagnostics
                | _contact_diagnostics(selection.debug)
                | {
                    "message": _failure_message(selection.status, selection.debug.rejected_side),
                },
            )

        quality = max(params.min_quality, min(0.98, 0.62 + 0.3 * contrast_quality))
        result = valid_result(
            target_family=self.target_family,
            detector=self.detector_kind,
            selection=selection,
            contour_area_px=float(np.count_nonzero(foreground)),
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
                "point_a_local": selection.point_a_local,
                "point_b_local": selection.point_b_local,
                "measurement_line_y": selection.measurement_line_y,
                "local_y_delta_px": selection.local_y_delta_px,
                "parallel_error_px": selection.parallel_error_px,
                "chord_length_px": selection.chord_length_px,
                "pattern_model": selection.pattern_model,
                "detected_pattern": selection.detected_pattern,
                "object_interval_count": selection.object_interval_count,
                "interval_count": selection.interval_count,
                "selected_intervals": selection.selected_intervals,
                "raw_intervals": selection.raw_intervals,
                "bridged_intervals": selection.bridged_intervals,
                "selected_valid_intervals": selection.selected_valid_intervals,
                "leftmost_valid_interval": selection.leftmost_valid_interval,
                "rightmost_valid_interval": selection.rightmost_valid_interval,
                "formal_point_a_source_interval": selection.formal_point_a_source_interval,
                "formal_point_b_source_interval": selection.formal_point_b_source_interval,
                "point_a_on_foreground_boundary": selection.point_a_on_foreground_boundary,
                "point_b_on_foreground_boundary": selection.point_b_on_foreground_boundary,
                "point_a_source_layer": selection.point_a_source_layer,
                "point_b_source_layer": selection.point_b_source_layer,
                "internal_gap_count": selection.internal_gap_count,
                "max_internal_gap_px": selection.max_internal_gap_px,
                "bundle_outer_span_px": selection.bundle_outer_span_px,
                "formal_ab_span_px": selection.formal_ab_span_px,
                "virtual_envelope_span_px": selection.virtual_envelope_span_px,
                "candidate_line_is_debug_only": selection.candidate_line_is_debug_only,
                "selected_line_reason": selection.selected_line_reason,
                "measurement_mode": selection.measurement_mode,
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


def _segmentation_diagnostics(segmentation_debug: object) -> dict[str, object]:
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
        "foreground_area_px": segmentation_debug.foreground_area_px,
        "foreground_area_ratio_in_roi": segmentation_debug.foreground_area_ratio_in_roi,
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
        "point_a_local": contact_debug.point_a_local,
        "point_b_local": contact_debug.point_b_local,
        "measurement_line_y": contact_debug.measurement_line_y,
        "local_y_delta_px": contact_debug.local_y_delta_px,
        "parallel_error_px": contact_debug.parallel_error_px,
        "chord_length_px": contact_debug.chord_length_px,
        "pattern_model": contact_debug.pattern_model,
        "detected_pattern": contact_debug.detected_pattern,
        "object_interval_count": contact_debug.object_interval_count,
        "interval_count": contact_debug.interval_count,
        "selected_intervals": contact_debug.selected_intervals,
        "raw_intervals": contact_debug.raw_intervals,
        "bridged_intervals": contact_debug.bridged_intervals,
        "selected_valid_intervals": contact_debug.selected_valid_intervals,
        "leftmost_valid_interval": contact_debug.leftmost_valid_interval,
        "rightmost_valid_interval": contact_debug.rightmost_valid_interval,
        "formal_point_a_source_interval": contact_debug.formal_point_a_source_interval,
        "formal_point_b_source_interval": contact_debug.formal_point_b_source_interval,
        "point_a_on_foreground_boundary": contact_debug.point_a_on_foreground_boundary,
        "point_b_on_foreground_boundary": contact_debug.point_b_on_foreground_boundary,
        "point_a_source_layer": contact_debug.point_a_source_layer,
        "point_b_source_layer": contact_debug.point_b_source_layer,
        "internal_gap_count": contact_debug.internal_gap_count,
        "max_internal_gap_px": contact_debug.max_internal_gap_px,
        "bundle_outer_span_px": contact_debug.bundle_outer_span_px,
        "formal_ab_span_px": contact_debug.formal_ab_span_px,
        "virtual_envelope_span_px": contact_debug.virtual_envelope_span_px,
        "candidate_line_is_debug_only": contact_debug.candidate_line_is_debug_only,
        "selected_line_reason": contact_debug.selected_line_reason,
        "measurement_mode": contact_debug.measurement_mode,
    }


def _failure_message(status: DetectionStatus, rejected_side: str | None) -> str | None:
    if status is DetectionStatus.CALIPER_CONTACT_ON_ROI_BOUNDARY:
        side_text = rejected_side or "unknown"
        return f"Detected contour contact is too close to the {side_text} ROI measurement boundary."
    return None
