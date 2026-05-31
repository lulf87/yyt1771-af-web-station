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
            params=params,
        )
        timings_ms["wire_filtering_ms"] = elapsed_ms(wire_filtering_start)
        bundle_internal_gap_px = _effective_bundle_internal_gap_px(params, roi)
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
            "max_internal_gap_px": params.max_internal_gap_px
            if params.max_internal_gap_px is not None
            else params.max_internal_gap_ratio * roi.width,
            "max_bundle_internal_gap_px": bundle_internal_gap_px,
            "max_bundle_internal_gap_ratio": params.max_bundle_internal_gap_ratio,
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
            min_mesh_interval_width_px=params.min_interval_width_px,
            min_mesh_interval_count=params.min_valid_interval_count,
            max_mesh_interval_width_ratio=params.max_interval_width_ratio,
            min_neighbor_support_lines=(
                params.min_neighbor_line_support
                if params.enable_neighbor_line_support_filter
                else 0
            ),
            bundle_detected_pattern="wire_bundle_envelope",
            prefer_largest_formal_span=True,
            reject_global_foreground_boundary=False,
            max_internal_gap_px=(
                bundle_internal_gap_px if params.enable_remote_interval_rejection else None
            ),
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
        invariant_violation = invariant_violation or _wire_source_invariant(
            selection=selection,
            roi=roi,
            foreground=wire_foreground,
        )
        if invariant_violation is not None:
            return _timed_failure(
                DetectionStatus.COORDINATE_MAPPING_ERROR,
                quality=contrast_quality,
                contour_area_px=float(np.count_nonzero(foreground)),
                candidate_components=len(components),
                diagnostics_extra=component_diagnostics
                | _selection_diagnostics(selection, include_full=True)
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
            }
            | _selection_diagnostics(selection, include_full=wants_full)
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


def _effective_bundle_internal_gap_px(
    params: WireStripDetectorParams,
    roi: RotatedRoi,
) -> float:
    ratio_limit = params.max_bundle_internal_gap_ratio * roi.width
    if params.max_bundle_internal_gap_px is None:
        return float(ratio_limit)
    return float(min(params.max_bundle_internal_gap_px, ratio_limit))


def _wire_likeness_diagnostics(analysis: WireForegroundAnalysis) -> dict[str, object]:
    primary = _primary_metric(analysis)
    component_orientation = primary.orientation_deg if primary is not None else None
    return {
        "broad_blob_rejection_count": analysis.broad_blob_rejection_count,
        "broad_blob_area_ratio": analysis.broad_blob_area_ratio,
        "local_contrast_score": primary.local_contrast if primary is not None else None,
        "wire_likeness_score": analysis.primary_wire_likeness_score,
        "component_area_px": primary.area_px if primary is not None else None,
        "component_bbox": primary.bbox if primary is not None else None,
        "component_aspect_ratio": analysis.primary_aspect_ratio,
        "component_orientation": component_orientation,
        "component_orientation_deg": component_orientation,
        "orientation_deviation_deg": (
            primary.orientation_deviation_deg if primary is not None else None
        ),
    }


def _selection_diagnostics(selection: object, *, include_full: bool) -> dict[str, object]:
    payload = {
        "point_a_local": getattr(selection, "point_a_local", None),
        "point_b_local": getattr(selection, "point_b_local", None),
        "measurement_line_y": getattr(selection, "measurement_line_y", None),
        "local_y_delta_px": getattr(selection, "local_y_delta_px", None),
        "parallel_error_px": getattr(selection, "parallel_error_px", None),
        "chord_length_px": getattr(selection, "chord_length_px", None),
        "pattern_model": getattr(selection, "pattern_model", None),
        "detected_pattern": getattr(selection, "detected_pattern", None),
        "object_interval_count": getattr(selection, "object_interval_count", None),
        "interval_count": getattr(selection, "interval_count", None),
        "bundle_cluster_count": getattr(selection, "bundle_cluster_count", None),
        "selected_bundle_cluster_id": getattr(selection, "selected_bundle_cluster_id", None),
        "selected_bundle_interval_count": getattr(
            selection,
            "selected_bundle_interval_count",
            None,
        ),
        "selected_bundle_outer_span_px": getattr(
            selection,
            "selected_bundle_outer_span_px",
            None,
        ),
        "selected_bundle_support_ratio": getattr(
            selection,
            "selected_bundle_support_ratio",
            None,
        ),
        "selected_bundle_max_internal_gap_px": getattr(
            selection,
            "selected_bundle_max_internal_gap_px",
            None,
        ),
        "max_bundle_internal_gap_px": getattr(selection, "max_bundle_internal_gap_px", None),
        "remote_interval_rejection_count": getattr(
            selection,
            "remote_interval_rejection_count",
            None,
        ),
        "point_a_source_interval": getattr(selection, "point_a_source_interval", None),
        "point_b_source_interval": getattr(selection, "point_b_source_interval", None),
        "formal_point_a_source_interval": getattr(
            selection,
            "formal_point_a_source_interval",
            None,
        ),
        "formal_point_b_source_interval": getattr(
            selection,
            "formal_point_b_source_interval",
            None,
        ),
        "point_a_on_foreground_boundary": getattr(
            selection,
            "point_a_on_foreground_boundary",
            None,
        ),
        "point_b_on_foreground_boundary": getattr(
            selection,
            "point_b_on_foreground_boundary",
            None,
        ),
        "point_a_source_layer": getattr(selection, "point_a_source_layer", None),
        "point_b_source_layer": getattr(selection, "point_b_source_layer", None),
        "internal_gap_count": getattr(selection, "internal_gap_count", None),
        "max_internal_gap_px": getattr(selection, "max_internal_gap_px", None),
        "bundle_outer_span_px": getattr(selection, "bundle_outer_span_px", None),
        "formal_ab_span_px": getattr(selection, "formal_ab_span_px", None),
        "candidate_line_is_debug_only": getattr(selection, "candidate_line_is_debug_only", None),
        "selected_line_reason": getattr(selection, "selected_line_reason", None),
        "measurement_mode": getattr(selection, "measurement_mode", None),
        "neighbor_line_support": getattr(selection, "neighbor_line_support", None),
    }
    if include_full:
        payload |= {
            "selected_intervals": getattr(selection, "selected_intervals", None),
            "raw_intervals": getattr(selection, "raw_intervals", None),
            "bridged_intervals": getattr(selection, "bridged_intervals", None),
            "selected_valid_intervals": getattr(selection, "selected_valid_intervals", None),
            "leftmost_valid_interval": getattr(selection, "leftmost_valid_interval", None),
            "rightmost_valid_interval": getattr(selection, "rightmost_valid_interval", None),
            "interval_gaps": getattr(selection, "interval_gaps", None),
            "bundle_clusters": getattr(selection, "bundle_clusters", None),
            "rejected_remote_intervals": getattr(selection, "rejected_remote_intervals", None),
            "rejected_remote_interval_reasons": getattr(
                selection,
                "rejected_remote_interval_reasons",
                None,
            ),
            "mesh_outer_span_px": getattr(selection, "mesh_outer_span_px", None),
            "virtual_envelope_span_px": getattr(selection, "virtual_envelope_span_px", None),
        }
    else:
        payload |= {
            "selected_intervals": None,
            "raw_intervals": None,
            "bridged_intervals": None,
            "selected_valid_intervals": None,
            "leftmost_valid_interval": None,
            "rightmost_valid_interval": None,
            "interval_gaps": None,
            "bundle_clusters": None,
            "rejected_remote_intervals": None,
            "rejected_remote_interval_reasons": None,
            "mesh_outer_span_px": None,
            "virtual_envelope_span_px": None,
        }
    return payload


def _wire_source_invariant(
    *,
    selection: object,
    roi: RotatedRoi,
    foreground: np.ndarray,
    tolerance_px: float = 1.0,
) -> str | None:
    if getattr(selection, "measurement_mode", None) != "wire_bundle_envelope":
        return None
    point_a_local = getattr(selection, "point_a_local", None)
    point_b_local = getattr(selection, "point_b_local", None)
    point_a_source = getattr(selection, "point_a_source_interval", None) or getattr(
        selection, "formal_point_a_source_interval", None
    )
    point_b_source = getattr(selection, "point_b_source_interval", None) or getattr(
        selection, "formal_point_b_source_interval", None
    )
    selected_intervals = getattr(selection, "selected_valid_intervals", None)
    rejected_remote = getattr(selection, "rejected_remote_intervals", None) or []
    if point_a_local is None or point_b_local is None:
        return "wire_source_local_point_missing"
    if point_a_source is None or point_b_source is None:
        return "wire_source_interval_missing"
    if not isinstance(selected_intervals, list) or not selected_intervals:
        return "wire_selected_intervals_missing"
    if point_a_source not in selected_intervals:
        return "point_a_source_not_selected_interval"
    if point_b_source not in selected_intervals:
        return "point_b_source_not_selected_interval"
    if point_a_source in rejected_remote:
        return "point_a_source_is_rejected_interval"
    if point_b_source in rejected_remote:
        return "point_b_source_is_rejected_interval"
    if getattr(point_a_source, "rejected", False):
        return "point_a_source_marked_rejected"
    if getattr(point_b_source, "rejected", False):
        return "point_b_source_marked_rejected"
    measurement_line_y = getattr(selection, "measurement_line_y", None)
    if not isinstance(measurement_line_y, int | float):
        return "wire_measurement_line_missing"
    if abs(point_a_local.y - measurement_line_y) > tolerance_px:
        return "point_a_not_on_measurement_line"
    if abs(point_b_local.y - measurement_line_y) > tolerance_px:
        return "point_b_not_on_measurement_line"
    local_y_delta = getattr(selection, "local_y_delta_px", 0.0)
    if isinstance(local_y_delta, int | float) and abs(local_y_delta) > tolerance_px:
        return "local_y_delta_exceeds_tolerance"
    parallel_error = getattr(selection, "parallel_error_px", 0.0)
    if isinstance(parallel_error, int | float) and abs(parallel_error) > tolerance_px:
        return "parallel_error_exceeds_tolerance"
    if abs(point_a_local.x - point_a_source.start_local_x) > tolerance_px:
        return "point_a_not_source_left_boundary"
    if abs(point_b_local.x - point_b_source.end_local_x) > tolerance_px:
        return "point_b_not_source_right_boundary"
    if not _source_boundary_on_foreground(
        foreground,
        roi,
        point_a_source.start_local_x,
        measurement_line_y,
        outside_direction=-1.0,
    ):
        return "point_a_not_foreground_boundary"
    if not _source_boundary_on_foreground(
        foreground,
        roi,
        point_b_source.end_local_x,
        measurement_line_y,
        outside_direction=1.0,
    ):
        return "point_b_not_foreground_boundary"
    return None


def _source_boundary_on_foreground(
    foreground: np.ndarray,
    roi: RotatedRoi,
    local_x: float,
    local_y: float,
    *,
    outside_direction: float,
) -> bool:
    if not _point_in_mask(foreground, roi, local_x, local_y):
        return False
    outside_x = local_x + outside_direction
    if outside_x < -roi.width / 2.0 or outside_x > roi.width / 2.0:
        return False
    return not _point_in_mask(foreground, roi, outside_x, local_y)


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
        metric = _reject_metric_at(components, analysis.metrics, roi, center_local_x, line_y)
        reason = metric.reject_reason if metric is not None else "background"
        rejected.append(
            interval.model_copy(
                update={
                    "rejected": True,
                    "reject_reason": reason,
                    "local_contrast_score": metric.local_contrast if metric else None,
                    "wire_likeness_score": metric.wire_likeness_score if metric else None,
                    "source_component_id": metric.component_id if metric else None,
                    "touches_roi_boundary": _interval_touches_roi_boundary(interval, roi),
                }
            )
        )
        reasons.append(reason)
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


def _reject_metric_at(
    components: list[BinaryComponent],
    metrics: list[WireComponentMetric],
    roi: RotatedRoi,
    local_x: float,
    local_y: float,
) -> WireComponentMetric | None:
    point = roi_local_to_acquisition_point(roi, local_x, local_y)
    px = int(round(point.x))
    py = int(round(point.y))
    for component, metric in zip(components, metrics, strict=False):
        if not (0 <= py < component.mask.shape[0] and 0 <= px < component.mask.shape[1]):
            continue
        if component.mask[py, px] and not metric.accepted:
            return metric
    return None


def _primary_metric(analysis: WireForegroundAnalysis) -> WireComponentMetric | None:
    accepted = [metric for metric in analysis.metrics if metric.accepted]
    if accepted:
        return max(accepted, key=lambda metric: metric.wire_likeness_score)
    if analysis.metrics:
        return max(analysis.metrics, key=lambda metric: metric.wire_likeness_score)
    return None


def _interval_touches_roi_boundary(interval: object, roi: RotatedRoi) -> bool:
    start = getattr(interval, "start_local_x", 0.0)
    end = getattr(interval, "end_local_x", 0.0)
    return bool(start <= -roi.width / 2.0 or end >= roi.width / 2.0)


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
        "interval_gaps": contact_debug.interval_gaps,
        "bundle_cluster_count": contact_debug.bundle_cluster_count,
        "bundle_clusters": contact_debug.bundle_clusters,
        "selected_bundle_cluster_id": contact_debug.selected_bundle_cluster_id,
        "selected_bundle_interval_count": contact_debug.selected_bundle_interval_count,
        "selected_bundle_outer_span_px": contact_debug.selected_bundle_outer_span_px,
        "selected_bundle_support_ratio": contact_debug.selected_bundle_support_ratio,
        "selected_bundle_max_internal_gap_px": contact_debug.selected_bundle_max_internal_gap_px,
        "max_bundle_internal_gap_px": contact_debug.max_bundle_internal_gap_px,
        "rejected_remote_intervals": contact_debug.rejected_remote_intervals,
        "rejected_remote_interval_reasons": contact_debug.rejected_remote_interval_reasons,
        "remote_interval_rejection_count": contact_debug.remote_interval_rejection_count,
        "point_a_source_interval": contact_debug.point_a_source_interval,
        "point_b_source_interval": contact_debug.point_b_source_interval,
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
