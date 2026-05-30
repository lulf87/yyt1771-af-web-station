from __future__ import annotations

import time

import numpy as np

from yyt1771_af.core.models import (
    BalloonEnvelopeDetectorParams,
    DetectionDiagnostics,
    DetectionResult,
    RotatedRoi,
    SegmentationParams,
)
from yyt1771_af.core.statuses import DetectionStatus, DetectorKind, TargetFamily
from yyt1771_af.vision.detection_debug import DebugLevel, wants_full_diagnostics
from yyt1771_af.vision.detector_timing import attach_detector_timings, elapsed_ms
from yyt1771_af.vision.roi_ops import (
    ContactRejection,
    assert_ab_invariants,
    component_bbox,
    component_roi_margins,
    extract_roi_crop,
    failure_result,
    rebase_result_to_acquisition,
    roi_is_inside_frame,
    rotated_roi_mask,
    select_roi_local_chord_contacts_debug,
    valid_result,
)
from yyt1771_af.vision.segmentation import (
    connected_components,
    fill_internal_holes,
    morphology_padding_px,
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
        debug_level: DebugLevel = "full",
    ) -> DetectionResult:
        detector_start = time.perf_counter()
        params = params or BalloonEnvelopeDetectorParams()
        segmentation = segmentation or _segmentation_defaults_for_params(params)

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
        params: BalloonEnvelopeDetectorParams,
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
        roi_area = max(1, int(np.count_nonzero(roi_mask)))
        segmentation_layers, contrast_quality, segmentation_debug = (
            segment_target_mask_layers_debug(
                frame,
                roi_mask,
                segmentation,
                preferred_point_xy=(roi.center_x, roi.center_y),
            )
        )
        timings_ms["segmentation_ms"] = elapsed_ms(segmentation_start)
        fill_holes_start = time.perf_counter()
        filled_envelope = fill_internal_holes(segmentation_layers.morphology_foreground) & roi_mask
        timings_ms["fill_holes_ms"] = elapsed_ms(fill_holes_start)
        contact_source_used = params.contact_source or "filled_envelope"
        foreground = _contact_source_mask(
            contact_source_used,
            raw_foreground=segmentation_layers.raw_foreground,
            bridged_foreground=segmentation_layers.morphology_foreground,
            filled_envelope=filled_envelope,
        )
        actual_contact_source_area_ratio = float(np.count_nonzero(foreground) / roi_area)
        fill_internal_holes_used = contact_source_used == "filled_envelope"
        layer_diagnostics = _segmentation_diagnostics(
            segmentation_debug,
            filled_envelope=filled_envelope,
            roi_area=roi_area,
            fill_internal_holes_used=fill_internal_holes_used,
            params=params,
            segmentation=segmentation,
            contact_source_used=contact_source_used,
            actual_contact_source_area_ratio=actual_contact_source_area_ratio,
        )
        if params.envelope_mode == "open_mesh" and contact_source_used == "filled_envelope":
            return _timed_failure(
                DetectionStatus.SEGMENTATION_FAILED,
                quality=contrast_quality,
                message="open_mesh formal A/B cannot use filled_envelope debug layer.",
                diagnostics_extra=layer_diagnostics
                | {
                    "candidate_line_is_debug_only": True,
                    "point_a_source_layer": None,
                    "point_b_source_layer": None,
                },
            )
        if not np.any(foreground):
            return _timed_failure(
                DetectionStatus.LOW_CONTRAST,
                quality=contrast_quality,
                diagnostics_extra=layer_diagnostics,
            )

        components_start = time.perf_counter()
        components = connected_components(foreground, segmentation.min_component_area_px)
        timings_ms["connected_components_ms"] = elapsed_ms(components_start)
        if not components:
            return _timed_failure(
                DetectionStatus.TARGET_NOT_FOUND,
                quality=contrast_quality,
                diagnostics_extra=layer_diagnostics | {"candidate_component_count": 0},
            )
        if (
            params.envelope_mode != "open_mesh"
            and len(components) > 1
            and components[1].area_px > components[0].area_px * 0.35
        ):
            return _timed_failure(
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
        if params.envelope_mode == "open_mesh":
            component_mask = np.zeros_like(foreground, dtype=bool)
            component_coordinates = []
            for mesh_component in components:
                component_mask |= mesh_component.mask
                component_coordinates.append(mesh_component.coordinates_yx)
            component = type(component)(
                mask=component_mask,
                coordinates_yx=np.vstack(component_coordinates),
            )
        chord_timings: dict[str, float] = {}
        selection = select_roi_local_chord_contacts_debug(
            component.mask,
            roi,
            pattern_model=params.measurement_model,
            boundary_margin_px=params.boundary_margin_px,
            reject_contact_on_roi_boundary=params.reject_contact_on_roi_boundary,
            allow_mesh_outer_span=params.envelope_mode == "open_mesh",
            source_layer=contact_source_used,
            raw_foreground_mask=segmentation_layers.raw_foreground,
            bridged_foreground_mask=segmentation_layers.morphology_foreground,
            filled_envelope_mask=filled_envelope,
            compute_debug_intervals=wants_full,
            timings_ms=chord_timings,
        )
        timings_ms["chord_scan_ms"] = chord_timings.get("line_scan_ms", 0.0)
        timings_ms["candidate_scoring_ms"] = chord_timings.get("candidate_scoring_ms", 0.0)
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
            return _timed_failure(
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

        invariant_violation = assert_ab_invariants(
            selection.point_a,
            selection.point_b,
            roi=roi,
            frame_shape=frame.shape,
            foreground_mask=component.mask,
        )
        if invariant_violation is not None:
            return _timed_failure(
                DetectionStatus.COORDINATE_MAPPING_ERROR,
                quality=contrast_quality,
                contour_area_px=float(component.area_px),
                candidate_components=len(components),
                diagnostics_extra=component_diagnostics
                | {"message": f"Formal A/B invariant violation: {invariant_violation}"},
            )

        diagnostics_start = time.perf_counter()
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
                "point_a_local": selection.point_a_local,
                "point_b_local": selection.point_b_local,
                "measurement_line_y": selection.measurement_line_y,
                "local_y_delta_px": selection.local_y_delta_px,
                "parallel_error_px": selection.parallel_error_px,
                "chord_length_px": selection.chord_length_px,
                "pattern_model": selection.pattern_model,
                "detected_pattern": selection.detected_pattern,
                "object_interval_count": selection.object_interval_count,
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
                "mesh_outer_span_px": selection.mesh_outer_span_px,
                "formal_ab_span_px": selection.formal_ab_span_px,
                "virtual_envelope_span_px": selection.virtual_envelope_span_px,
                "candidate_line_is_debug_only": selection.candidate_line_is_debug_only,
            }
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


def _segmentation_diagnostics(
    segmentation_debug: object,
    *,
    filled_envelope: np.ndarray,
    roi_area: int,
    fill_internal_holes_used: bool,
    params: BalloonEnvelopeDetectorParams,
    segmentation: SegmentationParams,
    contact_source_used: str,
    actual_contact_source_area_ratio: float,
) -> dict[str, object]:
    filled_area = int(np.count_nonzero(filled_envelope))
    return {
        "envelope_mode": params.envelope_mode,
        "configured_contact_source": params.contact_source,
        "contact_source_used": contact_source_used,
        "actual_contact_source_area_ratio": actual_contact_source_area_ratio,
        "threshold_mode": segmentation.threshold_mode,
        "configured_polarity": segmentation.polarity,
        "close_kernel": segmentation.close_kernel,
        "open_kernel": segmentation.open_kernel,
        "min_component_area_px": segmentation.min_component_area_px,
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
        "bridged_foreground_ratio": segmentation_debug.morphology_foreground_ratio,
        "morphology_foreground_area_px": segmentation_debug.morphology_foreground_area_px,
        "morphology_foreground_ratio": segmentation_debug.morphology_foreground_ratio,
        "filled_envelope_area_px": filled_area,
        "filled_envelope_ratio": float(filled_area / max(1, roi_area)),
        "foreground_area_px": segmentation_debug.foreground_area_px,
        "foreground_area_ratio_in_roi": segmentation_debug.foreground_area_ratio_in_roi,
        "fill_internal_holes_used": fill_internal_holes_used,
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
        "mesh_outer_span_px": contact_debug.mesh_outer_span_px,
        "formal_ab_span_px": contact_debug.formal_ab_span_px,
        "virtual_envelope_span_px": contact_debug.virtual_envelope_span_px,
        "candidate_line_is_debug_only": contact_debug.candidate_line_is_debug_only,
        "measurement_mode": contact_debug.measurement_mode,
    }


def _component_margin_diagnostics(component: object, roi: RotatedRoi) -> dict[str, object]:
    margins = component_roi_margins(component, roi)
    return {
        "left_margin_px": margins.left_margin_px,
        "right_margin_px": margins.right_margin_px,
        "top_margin_px": margins.top_margin_px,
        "bottom_margin_px": margins.bottom_margin_px,
    }


def _segmentation_defaults_for_params(params: BalloonEnvelopeDetectorParams) -> SegmentationParams:
    if params.envelope_mode == "open_mesh":
        return SegmentationParams(
            polarity="dark_on_light",
            threshold_mode="fixed",
            threshold_value=160,
            fill_internal_holes=False,
        )
    return SegmentationParams(fill_internal_holes=params.fill_internal_holes)


def _contact_source_mask(
    contact_source: str,
    *,
    raw_foreground: np.ndarray,
    bridged_foreground: np.ndarray,
    filled_envelope: np.ndarray,
) -> np.ndarray:
    if contact_source == "raw_foreground":
        return raw_foreground
    if contact_source == "bridged_foreground":
        return bridged_foreground
    return filled_envelope


def _failure_message(status: DetectionStatus, rejected_side: str | None) -> str | None:
    if status is DetectionStatus.CALIPER_CONTACT_ON_ROI_BOUNDARY:
        side_text = rejected_side or "unknown"
        return f"Detected contour contact is too close to the {side_text} ROI measurement boundary."
    return None
