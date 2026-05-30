from __future__ import annotations

import time

import numpy as np

from yyt1771_af.core.models import (
    DetectionDiagnostics,
    DetectionResult,
    RotatedRoi,
    SegmentationParams,
    WireStripDetectorParams,
)
from yyt1771_af.core.statuses import DetectionStatus, DetectorKind, TargetFamily
from yyt1771_af.vision.detection_debug import DebugLevel, wants_full_diagnostics
from yyt1771_af.vision.detector_timing import attach_detector_timings, elapsed_ms
from yyt1771_af.vision.roi_ops import (
    ContactRejection,
    assert_ab_invariants,
    component_bbox,
    extract_roi_crop,
    failure_result,
    mask_bbox,
    mask_roi_margins,
    rebase_result_to_acquisition,
    roi_is_inside_frame,
    roi_local_to_acquisition_point,
    rotated_roi_mask,
    sample_line_intervals,
    select_roi_local_chord_contacts_debug,
    valid_result,
)
from yyt1771_af.vision.segmentation import (
    BinaryComponent,
    connected_components,
    morphology_padding_px,
    segment_target_mask_debug,
)
from yyt1771_af.vision.wire_filtering import (
    WireComponentMetric,
    WireForegroundAnalysis,
    analyze_wire_components,
)

# Internal wire-bundle spaces below this fraction of the ROI width are kept;
# larger gaps are treated as separation from non-target regions and split.
# Kept generous because component-level filtering already removes broad
# background blobs; this is only a coarse secondary guard.
_WIRE_MAX_INTERNAL_GAP_RATIO = 0.9


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
        debug_level: DebugLevel = "full",
    ) -> DetectionResult:
        detector_start = time.perf_counter()
        segmentation = segmentation or SegmentationParams()
        params = params or WireStripDetectorParams()

        if frame.ndim != 2:
            return attach_detector_timings(
                self._failure(
                    DetectionStatus.SEGMENTATION_FAILED,
                    message="Frame is not grayscale.",
                ),
                {},
                detector_start=detector_start,
            )
        if not roi_is_inside_frame(frame, roi):
            return attach_detector_timings(
                self._failure(
                    DetectionStatus.ROI_OUTSIDE_FRAME,
                    message="ROI is outside frame.",
                ),
                {},
                detector_start=detector_start,
            )

        crop = extract_roi_crop(frame, roi, padding_px=morphology_padding_px(segmentation))
        result = self._detect_cropped(
            frame=crop.frame,
            roi=crop.roi,
            segmentation=segmentation,
            params=params,
            debug_level=debug_level,
            detector_start=detector_start,
        )
        # ``extract_roi_crop`` returned crop-local acquisition coordinates; shift
        # every acquisition-space output back to true acquisition coordinates.
        rebase_result_to_acquisition(result, crop.offset_x, crop.offset_y)
        return result

    def _detect_cropped(
        self,
        *,
        frame: np.ndarray,
        roi: RotatedRoi,
        segmentation: SegmentationParams,
        params: WireStripDetectorParams,
        debug_level: DebugLevel,
        detector_start: float,
    ) -> DetectionResult:
        wants_full = wants_full_diagnostics(debug_level)
        timings_ms: dict[str, float] = {}

        def _timed_failure(
            status: DetectionStatus,
            *,
            quality: float = 0.0,
            contour_area_px: float | None = None,
            contour_point_count: int | None = None,
            candidate_components: int | None = None,
            message: str | None = None,
            diagnostics_extra: dict[str, object] | None = None,
        ) -> DetectionResult:
            diagnostics_start = time.perf_counter()
            result = self._failure(
                status,
                quality=quality,
                contour_area_px=contour_area_px,
                contour_point_count=contour_point_count,
                candidate_components=candidate_components,
                message=message,
                diagnostics_extra=diagnostics_extra,
            )
            timings_ms["diagnostics_ms"] = elapsed_ms(diagnostics_start)
            return attach_detector_timings(
                result,
                timings_ms,
                detector_start=detector_start,
            )

        segmentation_start = time.perf_counter()
        roi_mask = rotated_roi_mask(frame.shape, roi)
        foreground, contrast_quality, segmentation_debug = segment_target_mask_debug(
            frame,
            roi_mask,
            segmentation,
            preferred_point_xy=(roi.center_x, roi.center_y),
        )
        timings_ms["segmentation_ms"] = elapsed_ms(segmentation_start)
        if not np.any(foreground):
            return _timed_failure(
                DetectionStatus.LOW_CONTRAST,
                quality=contrast_quality,
                diagnostics_extra=_segmentation_diagnostics(segmentation_debug),
            )

        components_start = time.perf_counter()
        components = connected_components(foreground, segmentation.min_component_area_px)
        timings_ms["connected_components_ms"] = elapsed_ms(components_start)
        if not components:
            return _timed_failure(
                DetectionStatus.TARGET_NOT_FOUND,
                quality=contrast_quality,
                diagnostics_extra=_segmentation_diagnostics(segmentation_debug)
                | {"candidate_component_count": 0},
            )
        wire_filtering_start = time.perf_counter()
        wire_analysis = analyze_wire_components(
            image=frame,
            roi=roi,
            roi_mask=roi_mask,
            foreground=foreground,
            components=components,
        )
        timings_ms["wire_filtering_ms"] = elapsed_ms(wire_filtering_start)
        recipe_diagnostics = {
            "boundary_margin_px": params.boundary_margin_px,
            "roi_half_width": roi.width / 2.0,
            "pattern_model": params.measurement_model,
            "measurement_mode": params.measurement_mode,
            "threshold_mode": segmentation.threshold_mode,
            "configured_polarity": segmentation.polarity,
            "close_kernel": segmentation.close_kernel,
            "open_kernel": segmentation.open_kernel,
            "min_component_area_px": segmentation.min_component_area_px,
        } | _wire_likeness_diagnostics(wire_analysis)

        # Phase 2: the formal line scan runs on the filtered wire foreground so
        # broad background blobs and low-contrast patches can no longer become
        # wire intervals. The raw segmentation foreground is kept for overlays.
        wire_foreground = wire_analysis.wire_foreground
        if not np.any(wire_foreground):
            return _timed_failure(
                DetectionStatus.TARGET_NOT_FOUND,
                quality=contrast_quality,
                candidate_components=len(components),
                diagnostics_extra=_segmentation_diagnostics(segmentation_debug)
                | {"candidate_component_count": len(components)}
                | recipe_diagnostics
                | (
                    _rejected_interval_diagnostics(
                        foreground=foreground,
                        analysis=wire_analysis,
                        components=components,
                        roi=roi,
                        line_y=0.0,
                    )
                    if wants_full
                    else {}
                )
                | {"message": "No wire-like foreground component remained after filtering."},
            )
        selection_timings: dict[str, float] = {}
        selection = select_roi_local_chord_contacts_debug(
            wire_foreground,
            roi,
            pattern_model=params.measurement_model,
            measurement_mode=params.measurement_mode,
            boundary_margin_px=params.boundary_margin_px,
            reject_contact_on_roi_boundary=params.reject_contact_on_roi_boundary,
            allow_mesh_outer_span=True,
            source_layer="wire_foreground",
            raw_foreground_mask=foreground,
            bridged_foreground_mask=wire_foreground,
            min_mesh_interval_count=2,
            bundle_detected_pattern="wire_bundle_envelope",
            prefer_largest_formal_span=True,
            reject_global_foreground_boundary=False,
            max_internal_gap_px=_WIRE_MAX_INTERNAL_GAP_RATIO * roi.width,
            compute_debug_intervals=wants_full,
            timings_ms=selection_timings,
        )
        timings_ms.update(selection_timings)
        selected_bbox = mask_bbox(wire_foreground)
        margins = mask_roi_margins(wire_foreground, roi)
        component_diagnostics = (
            _segmentation_diagnostics(segmentation_debug)
            | {
                "candidate_component_count": len(components),
                "selected_component_area_px": int(np.count_nonzero(wire_foreground)),
                "selected_component_bbox": selected_bbox or component_bbox(components[0]),
            }
            | recipe_diagnostics
        )
        if margins is not None:
            component_diagnostics |= {
                "left_margin_px": margins.left_margin_px,
                "right_margin_px": margins.right_margin_px,
                "top_margin_px": margins.top_margin_px,
                "bottom_margin_px": margins.bottom_margin_px,
            }
        if isinstance(selection, ContactRejection):
            return _timed_failure(
                selection.status,
                quality=contrast_quality,
                contour_area_px=float(np.count_nonzero(foreground)),
                contour_point_count=selection.debug.contour_point_count,
                candidate_components=len(components),
                diagnostics_extra=component_diagnostics
                | _contact_diagnostics(selection.debug)
                | {"neighbor_line_support": selection.debug.neighbor_line_support}
                | (
                    _rejected_interval_diagnostics(
                        foreground=foreground,
                        analysis=wire_analysis,
                        components=components,
                        roi=roi,
                        line_y=selection.debug.measurement_line_y,
                    )
                    if wants_full
                    else {}
                )
                | {
                    "message": _failure_message(selection.status, selection.debug.rejected_side),
                },
            )

        invariant_violation = assert_ab_invariants(
            selection.point_a,
            selection.point_b,
            roi=roi,
            frame_shape=frame.shape,
            foreground_mask=wire_foreground,
        )
        if invariant_violation is not None:
            return _timed_failure(
                DetectionStatus.COORDINATE_MAPPING_ERROR,
                quality=contrast_quality,
                contour_area_px=float(np.count_nonzero(foreground)),
                candidate_components=len(components),
                diagnostics_extra=component_diagnostics
                | {"message": f"Formal A/B invariant violation: {invariant_violation}"},
            )

        diagnostics_start = time.perf_counter()
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
                "neighbor_line_support": selection.neighbor_line_support,
            }
            | (
                _rejected_interval_diagnostics(
                    foreground=foreground,
                    analysis=wire_analysis,
                    components=components,
                    roi=roi,
                    line_y=selection.measurement_line_y,
                )
                if wants_full
                else {}
            )
        )
        timings_ms["diagnostics_ms"] = elapsed_ms(diagnostics_start)
        return attach_detector_timings(
            result,
            timings_ms,
            detector_start=detector_start,
        )

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


def _wire_likeness_diagnostics(analysis: WireForegroundAnalysis) -> dict[str, object]:
    return {
        "broad_blob_rejection_count": analysis.broad_blob_rejection_count,
        "broad_blob_area_ratio": analysis.broad_blob_area_ratio,
        "wire_likeness_score": analysis.primary_wire_likeness_score,
        "component_aspect_ratio": analysis.primary_aspect_ratio,
        "component_orientation": analysis.primary_orientation_deg,
    }


def _rejected_interval_diagnostics(
    *,
    foreground: np.ndarray,
    analysis: WireForegroundAnalysis,
    components: list[BinaryComponent],
    roi: RotatedRoi,
    line_y: float | None,
) -> dict[str, object]:
    if line_y is None:
        return {}
    foreground_intervals = sample_line_intervals(foreground, roi, line_y)
    rejected = []
    reasons: list[str] = []
    for interval in foreground_intervals:
        center_local_x = (interval.start_local_x + interval.end_local_x) / 2.0
        if _point_in_mask(analysis.wire_foreground, roi, center_local_x, line_y):
            continue
        rejected.append(interval)
        reasons.append(_reject_reason_at(components, analysis.metrics, roi, center_local_x, line_y))
    if not rejected:
        return {}
    return {"rejected_intervals": rejected, "rejected_interval_reasons": reasons}


def _point_in_mask(mask: np.ndarray, roi: RotatedRoi, local_x: float, local_y: float) -> bool:
    point = roi_local_to_acquisition_point(roi, local_x, local_y)
    px = int(round(point.x))
    py = int(round(point.y))
    if not (0 <= py < mask.shape[0] and 0 <= px < mask.shape[1]):
        return False
    return bool(mask[py, px])


def _reject_reason_at(
    components: list[BinaryComponent],
    metrics: list[WireComponentMetric],
    roi: RotatedRoi,
    local_x: float,
    local_y: float,
) -> str:
    point = roi_local_to_acquisition_point(roi, local_x, local_y)
    px = int(round(point.x))
    py = int(round(point.y))
    for component, metric in zip(components, metrics, strict=False):
        if not (0 <= py < component.mask.shape[0] and 0 <= px < component.mask.shape[1]):
            continue
        if component.mask[py, px] and not metric.accepted:
            return metric.reject_reason or "rejected"
    return "background"


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
