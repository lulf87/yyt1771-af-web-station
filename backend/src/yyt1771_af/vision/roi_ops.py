from __future__ import annotations

import time
from dataclasses import dataclass, replace

import numpy as np

from yyt1771_af.core.geometry import euclidean_distance, roi_inside_frame, roi_measurement_direction
from yyt1771_af.core.models import (
    ComponentBBox,
    DetectionDiagnostics,
    DetectionResult,
    ObjectInterval,
    Point2D,
    RotatedRoi,
)
from yyt1771_af.core.statuses import CoordinateSpace, DetectionStatus, DetectorKind, TargetFamily
from yyt1771_af.vision.segmentation import BinaryComponent, contour_mask


@dataclass(frozen=True, slots=True)
class RoiCropWindow:
    frame: np.ndarray
    roi: RotatedRoi
    offset_y: int
    offset_x: int


def extract_roi_crop(
    frame: np.ndarray,
    roi: RotatedRoi,
    *,
    padding_px: int,
    border_fill: int = 255,
) -> RoiCropWindow:
    height, width = frame.shape[:2]
    half_w = roi.width / 2.0
    half_h = roi.height / 2.0
    unit_x, unit_y = roi_measurement_direction(roi.angle_deg)
    perp_x, perp_y = -unit_y, unit_x
    corner_x: list[float] = []
    corner_y: list[float] = []
    for local_x, local_y in (
        (-half_w, -half_h),
        (half_w, -half_h),
        (half_w, half_h),
        (-half_w, half_h),
    ):
        corner_x.append(roi.center_x + local_x * unit_x + local_y * perp_x)
        corner_y.append(roi.center_y + local_x * unit_y + local_y * perp_y)
    y0 = max(0, int(np.floor(min(corner_y))) - padding_px)
    y1 = min(height, int(np.ceil(max(corner_y))) + padding_px + 1)
    x0 = max(0, int(np.floor(min(corner_x))) - padding_px)
    x1 = min(width, int(np.ceil(max(corner_x))) + padding_px + 1)
    crop_area = max(0, y1 - y0) * max(0, x1 - x0)
    frame_area = height * width
    if frame_area < 400_000 or crop_area >= frame_area // 3:
        return RoiCropWindow(frame=np.asarray(frame), roi=roi, offset_y=0, offset_x=0)

    crop = np.asarray(frame[y0:y1, x0:x1])
    pad = max(0, padding_px)
    if pad == 0:
        return RoiCropWindow(
            frame=crop,
            roi=roi.model_copy(
                update={
                    "center_x": roi.center_x - x0,
                    "center_y": roi.center_y - y0,
                }
            ),
            offset_y=y0,
            offset_x=x0,
        )
    padded = np.full(
        (crop.shape[0] + 2 * pad, crop.shape[1] + 2 * pad),
        border_fill,
        dtype=crop.dtype,
    )
    padded[pad : pad + crop.shape[0], pad : pad + crop.shape[1]] = crop
    return RoiCropWindow(
        frame=padded,
        roi=roi.model_copy(
            update={
                "center_x": roi.center_x - x0 + pad,
                "center_y": roi.center_y - y0 + pad,
            }
        ),
        offset_y=y0 - pad,
        offset_x=x0 - pad,
    )


@dataclass(frozen=True, slots=True)
class ContactSelection:
    point_a: Point2D
    point_b: Point2D
    distance_px: float
    contour_point_count: int
    min_local_projection: float
    max_local_projection: float
    distance_to_left_roi_boundary_px: float
    distance_to_right_roi_boundary_px: float
    point_a_local: Point2D | None = None
    point_b_local: Point2D | None = None
    measurement_line_y: float | None = None
    local_y_delta_px: float | None = None
    parallel_error_px: float | None = None
    chord_length_px: float | None = None
    pattern_model: str | None = None
    detected_pattern: str | None = None
    object_interval_count: int | None = None
    interval_count: int | None = None
    selected_intervals: list[ObjectInterval] | None = None
    raw_intervals: list[ObjectInterval] | None = None
    bridged_intervals: list[ObjectInterval] | None = None
    selected_valid_intervals: list[ObjectInterval] | None = None
    leftmost_valid_interval: ObjectInterval | None = None
    rightmost_valid_interval: ObjectInterval | None = None
    formal_point_a_source_interval: ObjectInterval | None = None
    formal_point_b_source_interval: ObjectInterval | None = None
    point_a_on_foreground_boundary: bool | None = None
    point_b_on_foreground_boundary: bool | None = None
    point_a_source_layer: str | None = None
    point_b_source_layer: str | None = None
    internal_gap_count: int | None = None
    max_internal_gap_px: float | None = None
    mesh_outer_span_px: float | None = None
    bundle_outer_span_px: float | None = None
    formal_ab_span_px: float | None = None
    virtual_envelope_span_px: float | None = None
    candidate_line_is_debug_only: bool | None = None
    selected_line_reason: str | None = None
    measurement_mode: str | None = None
    neighbor_line_support: int | None = None


@dataclass(frozen=True, slots=True)
class ContactDebug:
    contour_point_count: int | None = None
    min_local_projection: float | None = None
    max_local_projection: float | None = None
    roi_min_allowed_projection: float | None = None
    roi_max_allowed_projection: float | None = None
    distance_to_left_roi_boundary_px: float | None = None
    distance_to_right_roi_boundary_px: float | None = None
    rejected_side: str | None = None
    rejected_candidate_point_a: Point2D | None = None
    rejected_candidate_point_b: Point2D | None = None
    point_a_local: Point2D | None = None
    point_b_local: Point2D | None = None
    measurement_line_y: float | None = None
    local_y_delta_px: float | None = None
    parallel_error_px: float | None = None
    chord_length_px: float | None = None
    pattern_model: str | None = None
    detected_pattern: str | None = None
    object_interval_count: int | None = None
    interval_count: int | None = None
    selected_intervals: list[ObjectInterval] | None = None
    raw_intervals: list[ObjectInterval] | None = None
    bridged_intervals: list[ObjectInterval] | None = None
    selected_valid_intervals: list[ObjectInterval] | None = None
    leftmost_valid_interval: ObjectInterval | None = None
    rightmost_valid_interval: ObjectInterval | None = None
    formal_point_a_source_interval: ObjectInterval | None = None
    formal_point_b_source_interval: ObjectInterval | None = None
    point_a_on_foreground_boundary: bool | None = None
    point_b_on_foreground_boundary: bool | None = None
    point_a_source_layer: str | None = None
    point_b_source_layer: str | None = None
    internal_gap_count: int | None = None
    max_internal_gap_px: float | None = None
    mesh_outer_span_px: float | None = None
    bundle_outer_span_px: float | None = None
    formal_ab_span_px: float | None = None
    virtual_envelope_span_px: float | None = None
    candidate_line_is_debug_only: bool | None = None
    selected_line_reason: str | None = None
    measurement_mode: str | None = None
    neighbor_line_support: int | None = None


@dataclass(frozen=True, slots=True)
class ContactRejection:
    status: DetectionStatus
    debug: ContactDebug


@dataclass(frozen=True, slots=True)
class ComponentMargins:
    left_margin_px: float
    right_margin_px: float
    top_margin_px: float
    bottom_margin_px: float


@dataclass(frozen=True, slots=True)
class _LineCandidate:
    point_a: Point2D
    point_b: Point2D
    point_a_local: Point2D
    point_b_local: Point2D
    measurement_line_y: float
    chord_length_px: float
    intervals: list[ObjectInterval]
    pattern_model: str
    detected_pattern: str
    object_interval_count: int
    interval_count: int
    contour_point_count: int
    distance_to_left_roi_boundary_px: float
    distance_to_right_roi_boundary_px: float
    rejected_side: str | None = None
    measurement_mode: str | None = None
    raw_intervals: list[ObjectInterval] | None = None
    bridged_intervals: list[ObjectInterval] | None = None
    selected_valid_intervals: list[ObjectInterval] | None = None
    leftmost_valid_interval: ObjectInterval | None = None
    rightmost_valid_interval: ObjectInterval | None = None
    formal_point_a_source_interval: ObjectInterval | None = None
    formal_point_b_source_interval: ObjectInterval | None = None
    point_a_on_foreground_boundary: bool | None = None
    point_b_on_foreground_boundary: bool | None = None
    point_a_source_layer: str | None = None
    point_b_source_layer: str | None = None
    internal_gap_count: int | None = None
    max_internal_gap_px: float | None = None
    mesh_outer_span_px: float | None = None
    bundle_outer_span_px: float | None = None
    formal_ab_span_px: float | None = None
    virtual_envelope_span_px: float | None = None
    candidate_line_is_debug_only: bool | None = None
    selected_line_reason: str | None = None
    neighbor_line_support: int | None = None
    score: float = 0.0
    # When True the diagnostic raw/bridged/virtual-envelope intervals are computed
    # lazily (only if this candidate is the one selected) instead of for every
    # scanned line. Plain line candidates leave this False to keep them ``None``,
    # matching the original eager behaviour exactly.
    carries_debug_intervals: bool = False


def rotated_roi_mask(shape: tuple[int, int], roi: RotatedRoi) -> np.ndarray:
    height, width = shape
    y, x = np.indices((height, width))
    unit_x, unit_y = roi_measurement_direction(roi.angle_deg)
    perp_x, perp_y = -unit_y, unit_x
    dx = x - roi.center_x
    dy = y - roi.center_y
    local_x = dx * unit_x + dy * unit_y
    local_y = dx * perp_x + dy * perp_y
    return (np.abs(local_x) <= roi.width / 2.0) & (np.abs(local_y) <= roi.height / 2.0)


def roi_is_inside_frame(frame: np.ndarray, roi: RotatedRoi) -> bool:
    height, width = frame.shape[:2]
    return roi_inside_frame(roi, frame_width=width - 1, frame_height=height - 1)


def roi_local_to_acquisition_point(roi: RotatedRoi, local_x: float, local_y: float) -> Point2D:
    unit_x, unit_y = roi_measurement_direction(roi.angle_deg)
    perp_x, perp_y = -unit_y, unit_x
    return Point2D(
        x=roi.center_x + local_x * unit_x + local_y * perp_x,
        y=roi.center_y + local_x * unit_y + local_y * perp_y,
        coordinate_space=CoordinateSpace.ACQUISITION,
    )


def acquisition_to_roi_local_point(roi: RotatedRoi, point: Point2D) -> Point2D:
    unit_x, unit_y = roi_measurement_direction(roi.angle_deg)
    perp_x, perp_y = -unit_y, unit_x
    dx = point.x - roi.center_x
    dy = point.y - roi.center_y
    return Point2D(
        x=dx * unit_x + dy * unit_y,
        y=dx * perp_x + dy * perp_y,
        coordinate_space=CoordinateSpace.ROI_LOCAL,
    )


def rebase_result_to_acquisition(
    result: DetectionResult, offset_x: int, offset_y: int
) -> DetectionResult:
    """Translate every acquisition-space output by the crop offset, in place.

    ``extract_roi_crop`` shifts the frame and ROI into a small crop-local window
    so detection runs cheaply. Every acquisition-space point the detector
    produces (formal ``point_a``/``point_b`` and acquisition-space diagnostics
    such as ``preferred_point_xy``, ``rejected_candidate_point_a``/``_b`` and
    ``selected_component_bbox``) is therefore expressed in crop-local pixels and
    must be shifted back by ``(offset_x, offset_y)`` to become true acquisition
    coordinates.

    ROI-local fields, ``distance_px``, spans and interval ``local_x``/``line_y``
    values are translation-invariant and are left untouched, so the measured
    distance never changes.
    """
    if offset_x == 0 and offset_y == 0:
        return result
    result.point_a = _shift_acquisition_point(result.point_a, offset_x, offset_y)
    result.point_b = _shift_acquisition_point(result.point_b, offset_x, offset_y)
    diagnostics = result.diagnostics
    diagnostics.preferred_point_xy = _shift_acquisition_point(
        diagnostics.preferred_point_xy, offset_x, offset_y
    )
    diagnostics.rejected_candidate_point_a = _shift_acquisition_point(
        diagnostics.rejected_candidate_point_a, offset_x, offset_y
    )
    diagnostics.rejected_candidate_point_b = _shift_acquisition_point(
        diagnostics.rejected_candidate_point_b, offset_x, offset_y
    )
    diagnostics.selected_component_bbox = _shift_bbox(
        diagnostics.selected_component_bbox, offset_x, offset_y
    )
    return result


def assert_ab_invariants(
    point_a: Point2D | None,
    point_b: Point2D | None,
    *,
    roi: RotatedRoi,
    frame_shape: tuple[int, ...],
    foreground_mask: np.ndarray,
    boundary_tolerance_px: float = 1.0,
) -> str | None:
    """Validate formal A/B against the detection contract.

    Returns ``None`` when both points satisfy every invariant, otherwise a short
    reason string describing the first violation. The caller maps a non-``None``
    reason to :class:`DetectionStatus.COORDINATE_MAPPING_ERROR`.

    The points and masks are evaluated in the same (crop-local) coordinate space
    the detector worked in; because the crop ROI is the original ROI shifted by
    the same offset, ROI containment and foreground membership are identical
    before and after :func:`rebase_result_to_acquisition`.
    """
    height, width = int(frame_shape[0]), int(frame_shape[1])
    mask = np.asarray(foreground_mask, dtype=bool)
    half_width = roi.width / 2.0
    half_height = roi.height / 2.0
    for name, point in (("point_a", point_a), ("point_b", point_b)):
        if point is None:
            return f"{name}_missing"
        if point.coordinate_space is not CoordinateSpace.ACQUISITION:
            return f"{name}_not_acquisition"
        if not (
            -boundary_tolerance_px <= point.x <= width - 1 + boundary_tolerance_px
            and -boundary_tolerance_px <= point.y <= height - 1 + boundary_tolerance_px
        ):
            return f"{name}_outside_frame"
        local = acquisition_to_roi_local_point(roi, point)
        if (
            abs(local.x) > half_width + boundary_tolerance_px
            or abs(local.y) > half_height + boundary_tolerance_px
        ):
            return f"{name}_outside_roi"
        if not _point_near_mask(mask, point.x, point.y, radius=1):
            return f"{name}_off_foreground"
    return None


def _shift_acquisition_point(point: Point2D | None, offset_x: int, offset_y: int) -> Point2D | None:
    if point is None:
        return None
    if point.coordinate_space is not CoordinateSpace.ACQUISITION:
        return point
    return Point2D(
        x=point.x + offset_x,
        y=point.y + offset_y,
        coordinate_space=CoordinateSpace.ACQUISITION,
    )


def _shift_bbox(bbox: ComponentBBox | None, offset_x: int, offset_y: int) -> ComponentBBox | None:
    if bbox is None:
        return None
    return ComponentBBox(
        min_x=bbox.min_x + offset_x,
        min_y=bbox.min_y + offset_y,
        max_x=bbox.max_x + offset_x,
        max_y=bbox.max_y + offset_y,
    )


def _point_near_mask(mask: np.ndarray, x: float, y: float, *, radius: int) -> bool:
    if mask.size == 0:
        return False
    height, width = mask.shape[:2]
    px = int(round(x))
    py = int(round(y))
    y0 = max(0, py - radius)
    y1 = min(height, py + radius + 1)
    x0 = max(0, px - radius)
    x1 = min(width, px + radius + 1)
    if y1 <= y0 or x1 <= x0:
        return False
    return bool(np.any(mask[y0:y1, x0:x1]))


def select_roi_local_chord_contacts_debug(
    mask: np.ndarray,
    roi: RotatedRoi,
    *,
    pattern_model: str,
    boundary_margin_px: float,
    reject_contact_on_roi_boundary: bool,
    measurement_mode: str | None = None,
    line_step_px: float = 1.0,
    allow_mesh_outer_span: bool = False,
    source_layer: str = "foreground",
    raw_foreground_mask: np.ndarray | None = None,
    bridged_foreground_mask: np.ndarray | None = None,
    filled_envelope_mask: np.ndarray | None = None,
    min_mesh_interval_width_px: float = 3.0,
    min_mesh_interval_count: int = 2,
    max_mesh_interval_width_ratio: float = 0.65,
    min_neighbor_support_lines: int = 1,
    bundle_detected_pattern: str = "mesh_outer_span",
    prefer_largest_formal_span: bool = False,
    reject_global_foreground_boundary: bool = True,
    max_internal_gap_px: float | None = None,
    compute_debug_intervals: bool = True,
    timings_ms: dict[str, float] | None = None,
) -> ContactSelection | ContactRejection:
    line_scan_start = time.perf_counter()
    candidate_scoring_ms = 0.0

    def _finish_timing() -> None:
        if timings_ms is None:
            return
        timings_ms["candidate_scoring_ms"] = round(candidate_scoring_ms, 3)
        timings_ms["line_scan_ms"] = round(
            max(
                0.0,
                (time.perf_counter() - line_scan_start) * 1000.0 - candidate_scoring_ms,
            ),
            3,
        )

    foreground = np.asarray(mask, dtype=bool)
    edge_mask = contour_mask(foreground)
    contour_count = int(np.count_nonzero(edge_mask))
    if not np.any(foreground):
        _finish_timing()
        return ContactRejection(
            status=DetectionStatus.TARGET_NOT_FOUND,
            debug=_chord_debug(
                roi=roi,
                boundary_margin_px=boundary_margin_px,
                contour_point_count=contour_count,
                pattern_model=pattern_model,
                measurement_mode=measurement_mode,
            ),
        )
    global_margins = mask_roi_margins(foreground, roi)

    def _attach_debug_intervals(candidate: _LineCandidate | None) -> _LineCandidate | None:
        # Diagnostic-only intervals (raw/bridged foreground spans and the filled
        # envelope span) do not influence candidate scoring or selection, so they
        # are computed lazily for the single line that actually wins instead of
        # for every scanned line. This keeps formal A/B and status identical while
        # removing the dominant per-line debug cost during live playback. With
        # ``compute_debug_intervals=False`` (basic debug level) they are skipped
        # entirely, leaving the diagnostic fields ``None``.
        if (
            candidate is None
            or not candidate.carries_debug_intervals
            or not compute_debug_intervals
        ):
            return candidate
        return replace(
            candidate,
            raw_intervals=_debug_intervals(raw_foreground_mask, roi, candidate.measurement_line_y),
            bridged_intervals=_debug_intervals(
                bridged_foreground_mask, roi, candidate.measurement_line_y
            ),
            virtual_envelope_span_px=_virtual_span_px(
                filled_envelope_mask, roi, candidate.measurement_line_y
            ),
        )

    candidates: list[_LineCandidate] = []
    rejected_boundary: list[_LineCandidate] = []
    mismatched: list[_LineCandidate] = []
    for local_y in _measurement_line_values(roi, line_step_px):
        line_mask, local_x_values = _sample_mask_line(foreground, roi, local_y)
        intervals = _line_intervals(line_mask, local_x_values, local_y)
        if not intervals:
            continue
        scoring_start = time.perf_counter()
        if allow_mesh_outer_span:
            candidate = _build_mesh_outer_span_candidate(
                foreground=foreground,
                roi=roi,
                local_y=local_y,
                intervals=intervals,
                pattern_model=pattern_model,
                measurement_mode=measurement_mode,
                contour_point_count=contour_count,
                boundary_margin_px=boundary_margin_px,
                source_layer=source_layer,
                min_interval_width_px=min_mesh_interval_width_px,
                min_interval_count=min_mesh_interval_count,
                max_interval_width_ratio=max_mesh_interval_width_ratio,
                min_neighbor_support_lines=min_neighbor_support_lines,
                line_step_px=line_step_px,
                detected_pattern=bundle_detected_pattern,
                max_internal_gap_px=max_internal_gap_px,
                selected_line_reason=(
                    "max_formal_ab_span" if prefer_largest_formal_span else "highest_line_score"
                ),
            )
        else:
            candidate = _build_line_candidate(
                roi=roi,
                local_y=local_y,
                intervals=intervals,
                pattern_model=pattern_model,
                measurement_mode=measurement_mode,
                contour_point_count=contour_count,
            )
        candidate_scoring_ms += (time.perf_counter() - scoring_start) * 1000.0
        if candidate is None:
            # Debug intervals are attached lazily to the winning candidate only.
            mismatched.append(
                _mismatch_candidate(
                    roi=roi,
                    local_y=local_y,
                    intervals=intervals,
                    pattern_model=pattern_model,
                    measurement_mode=measurement_mode,
                    contour_point_count=contour_count,
                )
            )
            continue
        left_rejected = candidate.distance_to_left_roi_boundary_px <= boundary_margin_px
        right_rejected = candidate.distance_to_right_roi_boundary_px <= boundary_margin_px
        if reject_contact_on_roi_boundary and (left_rejected or right_rejected):
            rejected_boundary.append(
                _replace_rejected_side(
                    candidate,
                    _rejected_side(left_rejected, right_rejected),
                )
            )
            continue
        candidates.append(candidate)

    if candidates:
        candidate = _best_line_candidate(
            candidates,
            prefer_largest_formal_span=prefer_largest_formal_span,
        )
        if (
            global_margins is not None
            and reject_contact_on_roi_boundary
            and reject_global_foreground_boundary
        ):
            left_rejected = global_margins.left_margin_px <= boundary_margin_px
            right_rejected = global_margins.right_margin_px <= boundary_margin_px
            if left_rejected or right_rejected:
                candidate = (
                    _best_line_candidate(
                        rejected_boundary,
                        prefer_largest_formal_span=prefer_largest_formal_span,
                    )
                    if rejected_boundary
                    else candidate
                )
                _finish_timing()
                return ContactRejection(
                    status=DetectionStatus.CALIPER_CONTACT_ON_ROI_BOUNDARY,
                    debug=_candidate_to_debug(
                        _attach_debug_intervals(
                            _replace_rejected_side(
                                candidate,
                                _rejected_side(left_rejected, right_rejected),
                            )
                        ),
                        roi,
                        boundary_margin_px,
                    ),
                )
        _finish_timing()
        return _candidate_to_selection(_attach_debug_intervals(candidate))
    if rejected_boundary:
        candidate = _best_line_candidate(
            rejected_boundary,
            prefer_largest_formal_span=prefer_largest_formal_span,
        )
        _finish_timing()
        return ContactRejection(
            status=DetectionStatus.CALIPER_CONTACT_ON_ROI_BOUNDARY,
            debug=_candidate_to_debug(_attach_debug_intervals(candidate), roi, boundary_margin_px),
        )
    if mismatched:
        candidate = _best_line_candidate(
            mismatched,
            prefer_largest_formal_span=prefer_largest_formal_span,
        )
        _finish_timing()
        return ContactRejection(
            status=DetectionStatus.OBJECT_INTERVAL_COUNT_MISMATCH,
            debug=_candidate_to_debug(_attach_debug_intervals(candidate), roi, boundary_margin_px),
        )
    _finish_timing()
    return ContactRejection(
        status=DetectionStatus.PATTERN_NOT_FOUND,
        debug=_chord_debug(
            roi=roi,
            boundary_margin_px=boundary_margin_px,
            contour_point_count=contour_count,
            pattern_model=pattern_model,
            measurement_mode=measurement_mode,
        ),
    )


def select_contact_points(
    component: BinaryComponent,
    roi: RotatedRoi,
    *,
    boundary_margin_px: float,
    reject_contact_on_roi_boundary: bool,
) -> ContactSelection | DetectionStatus:
    selection = select_contact_points_debug(
        component,
        roi,
        boundary_margin_px=boundary_margin_px,
        reject_contact_on_roi_boundary=reject_contact_on_roi_boundary,
    )
    if isinstance(selection, ContactRejection):
        return selection.status
    return selection


def select_contact_points_debug(
    component: BinaryComponent,
    roi: RotatedRoi,
    *,
    boundary_margin_px: float,
    reject_contact_on_roi_boundary: bool,
) -> ContactSelection | ContactRejection:
    edge_mask = contour_mask(component.mask)
    contour_yx = np.argwhere(edge_mask)
    if contour_yx.size == 0:
        return ContactRejection(
            status=DetectionStatus.POINTS_NOT_ON_CONTOUR,
            debug=_empty_contact_debug(roi, boundary_margin_px),
        )

    point_xy = np.column_stack((contour_yx[:, 1].astype(float), contour_yx[:, 0].astype(float)))
    unit_x, unit_y = roi_measurement_direction(roi.angle_deg)
    perp_x, perp_y = -unit_y, unit_x
    centered_x = point_xy[:, 0] - roi.center_x
    centered_y = point_xy[:, 1] - roi.center_y
    local_projection = centered_x * unit_x + centered_y * unit_y

    min_projection = float(np.min(local_projection))
    max_projection = float(np.max(local_projection))
    if max_projection - min_projection < 2.0:
        debug = _contact_debug(
            roi=roi,
            boundary_margin_px=boundary_margin_px,
            contour_point_count=int(contour_yx.shape[0]),
            min_projection=min_projection,
            max_projection=max_projection,
            point_a=None,
            point_b=None,
            rejected_side=None,
        )
        return ContactRejection(
            status=DetectionStatus.OPPOSING_CONTOUR_EDGES_MISSING,
            debug=debug,
        )

    local_perpendicular = centered_x * perp_x + centered_y * perp_y
    min_index = _support_index(local_projection, local_perpendicular, min_projection)
    max_index = _support_index(local_projection, local_perpendicular, max_projection)
    point_a = Point2D(
        x=float(point_xy[min_index, 0]),
        y=float(point_xy[min_index, 1]),
        coordinate_space=CoordinateSpace.ACQUISITION,
    )
    point_b = Point2D(
        x=float(point_xy[max_index, 0]),
        y=float(point_xy[max_index, 1]),
        coordinate_space=CoordinateSpace.ACQUISITION,
    )

    distance_left = min_projection + roi.width / 2.0
    distance_right = roi.width / 2.0 - max_projection
    left_rejected = distance_left <= boundary_margin_px
    right_rejected = distance_right <= boundary_margin_px
    if reject_contact_on_roi_boundary and (left_rejected or right_rejected):
        rejected_side = _rejected_side(left_rejected, right_rejected)
        debug = _contact_debug(
            roi=roi,
            boundary_margin_px=boundary_margin_px,
            contour_point_count=int(contour_yx.shape[0]),
            min_projection=min_projection,
            max_projection=max_projection,
            point_a=point_a,
            point_b=point_b,
            rejected_side=rejected_side,
        )
        return ContactRejection(
            status=DetectionStatus.CALIPER_CONTACT_ON_ROI_BOUNDARY,
            debug=debug,
        )
    return ContactSelection(
        point_a=point_a,
        point_b=point_b,
        distance_px=euclidean_distance(point_a, point_b),
        contour_point_count=int(contour_yx.shape[0]),
        min_local_projection=min_projection,
        max_local_projection=max_projection,
        distance_to_left_roi_boundary_px=distance_left,
        distance_to_right_roi_boundary_px=distance_right,
    )


def valid_result(
    *,
    target_family: TargetFamily,
    detector: DetectorKind,
    selection: ContactSelection,
    contour_area_px: float,
    candidate_components: int,
    quality: float,
) -> DetectionResult:
    return DetectionResult(
        status=DetectionStatus.OK,
        valid=True,
        point_a=selection.point_a,
        point_b=selection.point_b,
        distance_px=selection.distance_px,
        quality=quality,
        target_family=target_family,
        diagnostics=DetectionDiagnostics(
            detector=detector,
            contour_area_px=contour_area_px,
            contour_point_count=selection.contour_point_count,
            candidate_components=candidate_components,
            candidate_component_count=candidate_components,
            selected_component_area_px=int(contour_area_px),
            min_local_projection=selection.min_local_projection,
            max_local_projection=selection.max_local_projection,
            distance_to_left_roi_boundary_px=selection.distance_to_left_roi_boundary_px,
            distance_to_right_roi_boundary_px=selection.distance_to_right_roi_boundary_px,
            point_a_local=selection.point_a_local,
            point_b_local=selection.point_b_local,
            measurement_line_y=selection.measurement_line_y,
            local_y_delta_px=selection.local_y_delta_px,
            parallel_error_px=selection.parallel_error_px,
            chord_length_px=selection.chord_length_px,
            pattern_model=selection.pattern_model,
            detected_pattern=selection.detected_pattern,
            object_interval_count=selection.object_interval_count,
            interval_count=selection.interval_count,
            selected_intervals=selection.selected_intervals,
            raw_intervals=selection.raw_intervals,
            bridged_intervals=selection.bridged_intervals,
            selected_valid_intervals=selection.selected_valid_intervals,
            leftmost_valid_interval=selection.leftmost_valid_interval,
            rightmost_valid_interval=selection.rightmost_valid_interval,
            formal_point_a_source_interval=selection.formal_point_a_source_interval,
            formal_point_b_source_interval=selection.formal_point_b_source_interval,
            point_a_on_foreground_boundary=selection.point_a_on_foreground_boundary,
            point_b_on_foreground_boundary=selection.point_b_on_foreground_boundary,
            point_a_source_layer=selection.point_a_source_layer,
            point_b_source_layer=selection.point_b_source_layer,
            internal_gap_count=selection.internal_gap_count,
            max_internal_gap_px=selection.max_internal_gap_px,
            mesh_outer_span_px=selection.mesh_outer_span_px,
            bundle_outer_span_px=selection.bundle_outer_span_px,
            formal_ab_span_px=selection.formal_ab_span_px,
            virtual_envelope_span_px=selection.virtual_envelope_span_px,
            candidate_line_is_debug_only=selection.candidate_line_is_debug_only,
            selected_line_reason=selection.selected_line_reason,
            measurement_mode=selection.measurement_mode,
        ),
    )


def failure_result(
    *,
    target_family: TargetFamily,
    detector: DetectorKind,
    status: DetectionStatus,
    quality: float = 0.0,
    contour_area_px: float | None = None,
    contour_point_count: int | None = None,
    candidate_components: int | None = None,
    message: str | None = None,
    diagnostics_extra: dict[str, object] | None = None,
) -> DetectionResult:
    diagnostics_payload = {
        "detector": detector,
        "contour_area_px": contour_area_px,
        "contour_point_count": contour_point_count,
        "candidate_components": candidate_components,
        "candidate_component_count": candidate_components,
        "message": message,
    }
    if diagnostics_extra:
        diagnostics_payload.update(diagnostics_extra)
    return DetectionResult(
        status=status,
        valid=False,
        point_a=None,
        point_b=None,
        distance_px=None,
        quality=quality,
        target_family=target_family,
        diagnostics=DetectionDiagnostics(**diagnostics_payload),
    )


def component_bbox(component: BinaryComponent) -> ComponentBBox:
    yx = component.coordinates_yx
    return ComponentBBox(
        min_x=int(np.min(yx[:, 1])),
        min_y=int(np.min(yx[:, 0])),
        max_x=int(np.max(yx[:, 1])),
        max_y=int(np.max(yx[:, 0])),
    )


def mask_bbox(mask: np.ndarray) -> ComponentBBox | None:
    yx = np.argwhere(np.asarray(mask, dtype=bool))
    if yx.size == 0:
        return None
    return ComponentBBox(
        min_x=int(np.min(yx[:, 1])),
        min_y=int(np.min(yx[:, 0])),
        max_x=int(np.max(yx[:, 1])),
        max_y=int(np.max(yx[:, 0])),
    )


def component_roi_margins(component: BinaryComponent, roi: RotatedRoi) -> ComponentMargins:
    point_xy = np.column_stack(
        (
            component.coordinates_yx[:, 1].astype(float),
            component.coordinates_yx[:, 0].astype(float),
        )
    )
    unit_x, unit_y = roi_measurement_direction(roi.angle_deg)
    perp_x, perp_y = -unit_y, unit_x
    centered_x = point_xy[:, 0] - roi.center_x
    centered_y = point_xy[:, 1] - roi.center_y
    local_x = centered_x * unit_x + centered_y * unit_y
    local_y = centered_x * perp_x + centered_y * perp_y
    return ComponentMargins(
        left_margin_px=float(np.min(local_x) + roi.width / 2.0),
        right_margin_px=float(roi.width / 2.0 - np.max(local_x)),
        top_margin_px=float(np.min(local_y) + roi.height / 2.0),
        bottom_margin_px=float(roi.height / 2.0 - np.max(local_y)),
    )


def mask_roi_margins(mask: np.ndarray, roi: RotatedRoi) -> ComponentMargins | None:
    yx = np.argwhere(np.asarray(mask, dtype=bool))
    if yx.size == 0:
        return None
    point_xy = np.column_stack((yx[:, 1].astype(float), yx[:, 0].astype(float)))
    unit_x, unit_y = roi_measurement_direction(roi.angle_deg)
    perp_x, perp_y = -unit_y, unit_x
    centered_x = point_xy[:, 0] - roi.center_x
    centered_y = point_xy[:, 1] - roi.center_y
    local_x = centered_x * unit_x + centered_y * unit_y
    local_y = centered_x * perp_x + centered_y * perp_y
    return ComponentMargins(
        left_margin_px=float(np.min(local_x) + roi.width / 2.0),
        right_margin_px=float(roi.width / 2.0 - np.max(local_x)),
        top_margin_px=float(np.min(local_y) + roi.height / 2.0),
        bottom_margin_px=float(roi.height / 2.0 - np.max(local_y)),
    )


def _measurement_line_values(roi: RotatedRoi, line_step_px: float) -> np.ndarray:
    half_height = roi.height / 2.0
    values = np.arange(-half_height, half_height + line_step_px * 0.5, line_step_px)
    if not np.any(np.isclose(values, 0.0)):
        values = np.append(values, 0.0)
    return np.asarray(sorted(values, key=lambda value: (abs(float(value)), float(value))))


def _sample_mask_line(
    mask: np.ndarray,
    roi: RotatedRoi,
    local_y: float,
) -> tuple[np.ndarray, np.ndarray]:
    half_width = roi.width / 2.0
    local_x_values = np.arange(-half_width, half_width + 0.5, 1.0)
    unit_x, unit_y = roi_measurement_direction(roi.angle_deg)
    perp_x, perp_y = -unit_y, unit_x
    acquisition_x = roi.center_x + local_x_values * unit_x + local_y * perp_x
    acquisition_y = roi.center_y + local_x_values * unit_y + local_y * perp_y
    pixel_x = np.rint(acquisition_x).astype(np.int64)
    pixel_y = np.rint(acquisition_y).astype(np.int64)
    valid = (pixel_x >= 0) & (pixel_y >= 0) & (pixel_x < mask.shape[1]) & (pixel_y < mask.shape[0])
    values = np.zeros(local_x_values.shape, dtype=bool)
    values[valid] = mask[pixel_y[valid], pixel_x[valid]]
    return values, local_x_values


def _line_intervals(
    line_mask: np.ndarray,
    local_x_values: np.ndarray,
    local_y: float,
) -> list[ObjectInterval]:
    intervals: list[ObjectInterval] = []
    start_index: int | None = None
    for index, value in enumerate(line_mask):
        if value and start_index is None:
            start_index = index
        elif not value and start_index is not None:
            intervals.append(
                _interval_from_indices(local_x_values, start_index, index - 1, local_y)
            )
            start_index = None
    if start_index is not None:
        intervals.append(
            _interval_from_indices(local_x_values, start_index, len(local_x_values) - 1, local_y)
        )
    return _merge_close_intervals(intervals, local_y)


def _interval_from_indices(
    local_x_values: np.ndarray,
    start_index: int,
    end_index: int,
    local_y: float,
) -> ObjectInterval:
    start_x = float(local_x_values[start_index])
    end_x = float(local_x_values[end_index])
    return ObjectInterval(
        start_local_x=start_x,
        end_local_x=end_x,
        width_px=max(0.0, end_x - start_x),
        line_y=float(local_y),
    )


def _merge_close_intervals(
    intervals: list[ObjectInterval],
    local_y: float,
    *,
    max_gap_px: float = 2.0,
) -> list[ObjectInterval]:
    if not intervals:
        return []
    merged: list[ObjectInterval] = [intervals[0]]
    for interval in intervals[1:]:
        previous = merged[-1]
        gap = interval.start_local_x - previous.end_local_x
        if gap <= max_gap_px:
            merged[-1] = ObjectInterval(
                start_local_x=previous.start_local_x,
                end_local_x=interval.end_local_x,
                width_px=max(0.0, interval.end_local_x - previous.start_local_x),
                line_y=float(local_y),
            )
        else:
            merged.append(interval)
    return merged


def _valid_mesh_intervals(
    intervals: list[ObjectInterval],
    *,
    roi: RotatedRoi,
    boundary_margin_px: float,
    min_interval_width_px: float,
    max_interval_width_ratio: float,
    enforce_boundary_margin: bool = True,
) -> list[ObjectInterval]:
    max_width = max_interval_width_ratio * roi.width
    valid: list[ObjectInterval] = []
    for interval in intervals:
        left_margin = interval.start_local_x + roi.width / 2.0
        right_margin = roi.width / 2.0 - interval.end_local_x
        if interval.width_px < min_interval_width_px:
            continue
        if interval.width_px > max_width:
            continue
        if enforce_boundary_margin and (
            left_margin <= boundary_margin_px or right_margin <= boundary_margin_px
        ):
            continue
        valid.append(interval)
    return valid


def sample_line_intervals(
    mask: np.ndarray,
    roi: RotatedRoi,
    local_y: float,
) -> list[ObjectInterval]:
    """Public helper: object intervals along one ROI-local measurement line."""
    line_mask, local_x_values = _sample_mask_line(np.asarray(mask, dtype=bool), roi, local_y)
    return _line_intervals(line_mask, local_x_values, local_y)


def _debug_intervals(
    mask: np.ndarray | None,
    roi: RotatedRoi,
    local_y: float,
) -> list[ObjectInterval] | None:
    if mask is None:
        return None
    line_mask, local_x_values = _sample_mask_line(np.asarray(mask, dtype=bool), roi, local_y)
    return _line_intervals(line_mask, local_x_values, local_y)


def _virtual_span_px(
    mask: np.ndarray | None,
    roi: RotatedRoi,
    local_y: float,
) -> float | None:
    intervals = _debug_intervals(mask, roi, local_y)
    if not intervals:
        return None
    return max(0.0, intervals[-1].end_local_x - intervals[0].start_local_x)


def _largest_gap_bounded_cluster(
    intervals: list[ObjectInterval],
    max_internal_gap_px: float,
) -> list[ObjectInterval]:
    """Split intervals where the gap exceeds the limit; keep the widest run.

    This prevents a remote dark region from being merged into the wire bundle
    envelope across a large internal gap. Internal wire-bundle spaces below the
    limit are preserved.
    """
    if len(intervals) < 2:
        return intervals
    clusters: list[list[ObjectInterval]] = [[intervals[0]]]
    for interval in intervals[1:]:
        gap = interval.start_local_x - clusters[-1][-1].end_local_x
        if gap <= max_internal_gap_px:
            clusters[-1].append(interval)
        else:
            clusters.append([interval])
    return max(
        clusters,
        key=lambda cluster: cluster[-1].end_local_x - cluster[0].start_local_x,
    )


def _interval_gaps(intervals: list[ObjectInterval]) -> list[float]:
    return [
        max(0.0, right.start_local_x - left.end_local_x)
        for left, right in zip(intervals, intervals[1:], strict=False)
    ]


def _neighbor_support_line_count(
    *,
    foreground: np.ndarray,
    roi: RotatedRoi,
    local_y: float,
    selected_intervals: list[ObjectInterval],
    boundary_margin_px: float,
    min_interval_width_px: float,
    max_interval_width_ratio: float,
    line_step_px: float,
) -> int:
    support = 0
    selected_start = selected_intervals[0].start_local_x
    selected_end = selected_intervals[-1].end_local_x
    for neighbor_y in (local_y - line_step_px, local_y + line_step_px):
        if abs(neighbor_y) > roi.height / 2.0:
            continue
        line_mask, local_x_values = _sample_mask_line(foreground, roi, neighbor_y)
        intervals = _valid_mesh_intervals(
            _line_intervals(line_mask, local_x_values, neighbor_y),
            roi=roi,
            boundary_margin_px=boundary_margin_px,
            min_interval_width_px=min_interval_width_px,
            max_interval_width_ratio=max_interval_width_ratio,
        )
        if len(intervals) < 2:
            continue
        neighbor_start = intervals[0].start_local_x
        neighbor_end = intervals[-1].end_local_x
        overlap = min(selected_end, neighbor_end) - max(selected_start, neighbor_start)
        if overlap > 0:
            support += 1
    return support


def _build_line_candidate(
    *,
    roi: RotatedRoi,
    local_y: float,
    intervals: list[ObjectInterval],
    pattern_model: str,
    measurement_mode: str | None,
    contour_point_count: int,
) -> _LineCandidate | None:
    expected_count = _expected_interval_count(pattern_model)
    if expected_count is None or len(intervals) != expected_count:
        return None
    if pattern_model == "blank_object_blank":
        point_a_x = intervals[0].start_local_x
        point_b_x = intervals[0].end_local_x
    else:
        point_a_x = intervals[0].start_local_x
        point_b_x = intervals[-1].end_local_x
    return _candidate_from_local_span(
        roi=roi,
        local_y=local_y,
        point_a_x=point_a_x,
        point_b_x=point_b_x,
        intervals=intervals,
        pattern_model=pattern_model,
        detected_pattern=_detected_pattern(len(intervals)),
        measurement_mode=measurement_mode,
        contour_point_count=contour_point_count,
    )


def _build_mesh_outer_span_candidate(
    *,
    foreground: np.ndarray,
    roi: RotatedRoi,
    local_y: float,
    intervals: list[ObjectInterval],
    pattern_model: str,
    measurement_mode: str | None,
    contour_point_count: int,
    boundary_margin_px: float,
    source_layer: str,
    min_interval_width_px: float,
    min_interval_count: int,
    max_interval_width_ratio: float,
    min_neighbor_support_lines: int,
    line_step_px: float,
    detected_pattern: str,
    selected_line_reason: str,
    max_internal_gap_px: float | None = None,
) -> _LineCandidate | None:
    supported_intervals = _valid_mesh_intervals(
        intervals,
        roi=roi,
        boundary_margin_px=boundary_margin_px,
        min_interval_width_px=min_interval_width_px,
        max_interval_width_ratio=max_interval_width_ratio,
        enforce_boundary_margin=False,
    )
    valid_intervals = _valid_mesh_intervals(
        supported_intervals,
        roi=roi,
        boundary_margin_px=boundary_margin_px,
        min_interval_width_px=min_interval_width_px,
        max_interval_width_ratio=max_interval_width_ratio,
    )
    if len(valid_intervals) < min_interval_count and len(supported_intervals) >= min_interval_count:
        valid_intervals = supported_intervals
    if len(valid_intervals) < min_interval_count:
        return None
    if max_internal_gap_px is not None:
        valid_intervals = _largest_gap_bounded_cluster(valid_intervals, max_internal_gap_px)
        if len(valid_intervals) < min_interval_count:
            return None
    has_boundary_contact = any(
        interval.start_local_x + roi.width / 2.0 <= boundary_margin_px
        or roi.width / 2.0 - interval.end_local_x <= boundary_margin_px
        for interval in valid_intervals
    )

    if has_boundary_contact:
        neighbor_support = 0
    else:
        neighbor_support = _neighbor_support_line_count(
            foreground=foreground,
            roi=roi,
            local_y=local_y,
            selected_intervals=valid_intervals,
            boundary_margin_px=boundary_margin_px,
            min_interval_width_px=min_interval_width_px,
            max_interval_width_ratio=max_interval_width_ratio,
            line_step_px=line_step_px,
        )
        if neighbor_support < min_neighbor_support_lines:
            return None

    leftmost = valid_intervals[0]
    rightmost = valid_intervals[-1]
    mesh_outer_span = max(0.0, rightmost.end_local_x - leftmost.start_local_x)
    gaps = _interval_gaps(valid_intervals)
    total_support_width = sum(interval.width_px for interval in valid_intervals)
    coverage_ratio = total_support_width / max(mesh_outer_span, 1.0)
    left_margin = leftmost.start_local_x + roi.width / 2.0
    right_margin = roi.width / 2.0 - rightmost.end_local_x
    max_gap = max(gaps) if gaps else 0.0
    score = (
        mesh_outer_span
        + len(valid_intervals) * 5.0
        + total_support_width * 0.25
        + coverage_ratio * 25.0
        + neighbor_support * 8.0
        + min(left_margin, right_margin) * 0.1
        - max_gap * 0.05
    )
    return _candidate_from_local_span(
        roi=roi,
        local_y=local_y,
        point_a_x=leftmost.start_local_x,
        point_b_x=rightmost.end_local_x,
        intervals=valid_intervals,
        pattern_model=pattern_model,
        detected_pattern=detected_pattern,
        measurement_mode=measurement_mode,
        contour_point_count=contour_point_count,
        selected_valid_intervals=valid_intervals,
        leftmost_valid_interval=leftmost,
        rightmost_valid_interval=rightmost,
        formal_point_a_source_interval=leftmost,
        formal_point_b_source_interval=rightmost,
        point_a_on_foreground_boundary=True,
        point_b_on_foreground_boundary=True,
        point_a_source_layer=source_layer,
        point_b_source_layer=source_layer,
        internal_gap_count=len(gaps),
        max_internal_gap_px=max_gap,
        mesh_outer_span_px=mesh_outer_span,
        bundle_outer_span_px=mesh_outer_span
        if detected_pattern == "wire_bundle_envelope"
        else None,
        formal_ab_span_px=mesh_outer_span,
        candidate_line_is_debug_only=False,
        selected_line_reason=selected_line_reason,
        neighbor_line_support=neighbor_support,
        score=score,
        carries_debug_intervals=True,
    )


def _mismatch_candidate(
    *,
    roi: RotatedRoi,
    local_y: float,
    intervals: list[ObjectInterval],
    pattern_model: str,
    measurement_mode: str | None,
    contour_point_count: int,
) -> _LineCandidate:
    return _candidate_from_local_span(
        roi=roi,
        local_y=local_y,
        point_a_x=intervals[0].start_local_x,
        point_b_x=intervals[-1].end_local_x,
        intervals=intervals,
        pattern_model=pattern_model,
        detected_pattern=_detected_pattern(len(intervals)),
        measurement_mode=measurement_mode,
        contour_point_count=contour_point_count,
        candidate_line_is_debug_only=True,
        carries_debug_intervals=True,
    )


def _candidate_from_local_span(
    *,
    roi: RotatedRoi,
    local_y: float,
    point_a_x: float,
    point_b_x: float,
    intervals: list[ObjectInterval],
    pattern_model: str,
    detected_pattern: str,
    measurement_mode: str | None,
    contour_point_count: int,
    raw_intervals: list[ObjectInterval] | None = None,
    bridged_intervals: list[ObjectInterval] | None = None,
    selected_valid_intervals: list[ObjectInterval] | None = None,
    leftmost_valid_interval: ObjectInterval | None = None,
    rightmost_valid_interval: ObjectInterval | None = None,
    formal_point_a_source_interval: ObjectInterval | None = None,
    formal_point_b_source_interval: ObjectInterval | None = None,
    point_a_on_foreground_boundary: bool | None = None,
    point_b_on_foreground_boundary: bool | None = None,
    point_a_source_layer: str | None = None,
    point_b_source_layer: str | None = None,
    internal_gap_count: int | None = None,
    max_internal_gap_px: float | None = None,
    mesh_outer_span_px: float | None = None,
    bundle_outer_span_px: float | None = None,
    formal_ab_span_px: float | None = None,
    virtual_envelope_span_px: float | None = None,
    candidate_line_is_debug_only: bool | None = None,
    selected_line_reason: str | None = None,
    neighbor_line_support: int | None = None,
    score: float = 0.0,
    carries_debug_intervals: bool = False,
) -> _LineCandidate:
    point_a_local = Point2D(
        x=float(point_a_x),
        y=float(local_y),
        coordinate_space=CoordinateSpace.ROI_LOCAL,
    )
    point_b_local = Point2D(
        x=float(point_b_x),
        y=float(local_y),
        coordinate_space=CoordinateSpace.ROI_LOCAL,
    )
    point_a = roi_local_to_acquisition_point(roi, point_a_local.x, point_a_local.y)
    point_b = roi_local_to_acquisition_point(roi, point_b_local.x, point_b_local.y)
    return _LineCandidate(
        point_a=point_a,
        point_b=point_b,
        point_a_local=point_a_local,
        point_b_local=point_b_local,
        measurement_line_y=float(local_y),
        chord_length_px=max(0.0, float(point_b_x - point_a_x)),
        intervals=intervals,
        pattern_model=pattern_model,
        detected_pattern=detected_pattern,
        object_interval_count=len(intervals),
        interval_count=len(intervals),
        contour_point_count=contour_point_count,
        distance_to_left_roi_boundary_px=float(point_a_x + roi.width / 2.0),
        distance_to_right_roi_boundary_px=float(roi.width / 2.0 - point_b_x),
        measurement_mode=measurement_mode,
        raw_intervals=raw_intervals,
        bridged_intervals=bridged_intervals,
        selected_valid_intervals=selected_valid_intervals,
        leftmost_valid_interval=leftmost_valid_interval,
        rightmost_valid_interval=rightmost_valid_interval,
        formal_point_a_source_interval=formal_point_a_source_interval,
        formal_point_b_source_interval=formal_point_b_source_interval,
        point_a_on_foreground_boundary=point_a_on_foreground_boundary,
        point_b_on_foreground_boundary=point_b_on_foreground_boundary,
        point_a_source_layer=point_a_source_layer,
        point_b_source_layer=point_b_source_layer,
        internal_gap_count=internal_gap_count,
        max_internal_gap_px=max_internal_gap_px,
        mesh_outer_span_px=mesh_outer_span_px,
        bundle_outer_span_px=bundle_outer_span_px,
        formal_ab_span_px=formal_ab_span_px,
        virtual_envelope_span_px=virtual_envelope_span_px,
        candidate_line_is_debug_only=candidate_line_is_debug_only,
        selected_line_reason=selected_line_reason,
        neighbor_line_support=neighbor_line_support,
        score=score,
        carries_debug_intervals=carries_debug_intervals,
    )


def _expected_interval_count(pattern_model: str) -> int | None:
    if pattern_model == "blank_object_blank":
        return 1
    return None


def _detected_pattern(interval_count: int) -> str:
    if interval_count == 1:
        return "blank_object_blank"
    if interval_count > 1:
        return "multiple_object_intervals"
    return "blank"


def _best_line_candidate(
    candidates: list[_LineCandidate],
    *,
    prefer_largest_formal_span: bool = False,
) -> _LineCandidate:
    if prefer_largest_formal_span:
        return max(
            candidates,
            key=lambda candidate: (
                candidate.formal_ab_span_px
                if candidate.formal_ab_span_px is not None
                else candidate.chord_length_px,
                candidate.score,
                candidate.chord_length_px,
                -abs(candidate.measurement_line_y),
            ),
        )
    return max(
        candidates,
        key=lambda candidate: (
            candidate.score,
            candidate.chord_length_px,
            -abs(candidate.measurement_line_y),
        ),
    )


def _replace_rejected_side(candidate: _LineCandidate, rejected_side: str | None) -> _LineCandidate:
    return _LineCandidate(
        point_a=candidate.point_a,
        point_b=candidate.point_b,
        point_a_local=candidate.point_a_local,
        point_b_local=candidate.point_b_local,
        measurement_line_y=candidate.measurement_line_y,
        chord_length_px=candidate.chord_length_px,
        intervals=candidate.intervals,
        pattern_model=candidate.pattern_model,
        detected_pattern=candidate.detected_pattern,
        object_interval_count=candidate.object_interval_count,
        interval_count=candidate.interval_count,
        contour_point_count=candidate.contour_point_count,
        distance_to_left_roi_boundary_px=candidate.distance_to_left_roi_boundary_px,
        distance_to_right_roi_boundary_px=candidate.distance_to_right_roi_boundary_px,
        rejected_side=rejected_side,
        measurement_mode=candidate.measurement_mode,
        raw_intervals=candidate.raw_intervals,
        bridged_intervals=candidate.bridged_intervals,
        selected_valid_intervals=candidate.selected_valid_intervals,
        leftmost_valid_interval=candidate.leftmost_valid_interval,
        rightmost_valid_interval=candidate.rightmost_valid_interval,
        formal_point_a_source_interval=candidate.formal_point_a_source_interval,
        formal_point_b_source_interval=candidate.formal_point_b_source_interval,
        point_a_on_foreground_boundary=candidate.point_a_on_foreground_boundary,
        point_b_on_foreground_boundary=candidate.point_b_on_foreground_boundary,
        point_a_source_layer=candidate.point_a_source_layer,
        point_b_source_layer=candidate.point_b_source_layer,
        internal_gap_count=candidate.internal_gap_count,
        max_internal_gap_px=candidate.max_internal_gap_px,
        mesh_outer_span_px=candidate.mesh_outer_span_px,
        bundle_outer_span_px=candidate.bundle_outer_span_px,
        formal_ab_span_px=candidate.formal_ab_span_px,
        virtual_envelope_span_px=candidate.virtual_envelope_span_px,
        candidate_line_is_debug_only=True
        if candidate.candidate_line_is_debug_only is None
        else candidate.candidate_line_is_debug_only,
        selected_line_reason=candidate.selected_line_reason,
        neighbor_line_support=candidate.neighbor_line_support,
        score=candidate.score,
        carries_debug_intervals=candidate.carries_debug_intervals,
    )


def _candidate_to_selection(candidate: _LineCandidate) -> ContactSelection:
    return ContactSelection(
        point_a=candidate.point_a,
        point_b=candidate.point_b,
        distance_px=euclidean_distance(candidate.point_a, candidate.point_b),
        contour_point_count=candidate.contour_point_count,
        min_local_projection=candidate.point_a_local.x,
        max_local_projection=candidate.point_b_local.x,
        distance_to_left_roi_boundary_px=candidate.distance_to_left_roi_boundary_px,
        distance_to_right_roi_boundary_px=candidate.distance_to_right_roi_boundary_px,
        point_a_local=candidate.point_a_local,
        point_b_local=candidate.point_b_local,
        measurement_line_y=candidate.measurement_line_y,
        local_y_delta_px=0.0,
        parallel_error_px=0.0,
        chord_length_px=candidate.chord_length_px,
        pattern_model=candidate.pattern_model,
        detected_pattern=candidate.detected_pattern,
        object_interval_count=candidate.object_interval_count,
        interval_count=candidate.interval_count,
        selected_intervals=candidate.intervals,
        raw_intervals=candidate.raw_intervals,
        bridged_intervals=candidate.bridged_intervals,
        selected_valid_intervals=candidate.selected_valid_intervals,
        leftmost_valid_interval=candidate.leftmost_valid_interval,
        rightmost_valid_interval=candidate.rightmost_valid_interval,
        formal_point_a_source_interval=candidate.formal_point_a_source_interval,
        formal_point_b_source_interval=candidate.formal_point_b_source_interval,
        point_a_on_foreground_boundary=candidate.point_a_on_foreground_boundary,
        point_b_on_foreground_boundary=candidate.point_b_on_foreground_boundary,
        point_a_source_layer=candidate.point_a_source_layer,
        point_b_source_layer=candidate.point_b_source_layer,
        internal_gap_count=candidate.internal_gap_count,
        max_internal_gap_px=candidate.max_internal_gap_px,
        mesh_outer_span_px=candidate.mesh_outer_span_px,
        bundle_outer_span_px=candidate.bundle_outer_span_px,
        formal_ab_span_px=candidate.formal_ab_span_px,
        virtual_envelope_span_px=candidate.virtual_envelope_span_px,
        candidate_line_is_debug_only=candidate.candidate_line_is_debug_only,
        selected_line_reason=candidate.selected_line_reason,
        measurement_mode=candidate.measurement_mode,
        neighbor_line_support=candidate.neighbor_line_support,
    )


def _candidate_to_debug(
    candidate: _LineCandidate,
    roi: RotatedRoi,
    boundary_margin_px: float,
) -> ContactDebug:
    return _chord_debug(
        roi=roi,
        boundary_margin_px=boundary_margin_px,
        contour_point_count=candidate.contour_point_count,
        min_projection=candidate.point_a_local.x,
        max_projection=candidate.point_b_local.x,
        point_a=candidate.point_a,
        point_b=candidate.point_b,
        point_a_local=candidate.point_a_local,
        point_b_local=candidate.point_b_local,
        rejected_side=candidate.rejected_side,
        measurement_line_y=candidate.measurement_line_y,
        local_y_delta_px=0.0,
        parallel_error_px=0.0,
        chord_length_px=candidate.chord_length_px,
        pattern_model=candidate.pattern_model,
        detected_pattern=candidate.detected_pattern,
        object_interval_count=candidate.object_interval_count,
        interval_count=candidate.interval_count,
        selected_intervals=candidate.intervals,
        raw_intervals=candidate.raw_intervals,
        bridged_intervals=candidate.bridged_intervals,
        selected_valid_intervals=candidate.selected_valid_intervals,
        leftmost_valid_interval=candidate.leftmost_valid_interval,
        rightmost_valid_interval=candidate.rightmost_valid_interval,
        formal_point_a_source_interval=candidate.formal_point_a_source_interval,
        formal_point_b_source_interval=candidate.formal_point_b_source_interval,
        point_a_on_foreground_boundary=candidate.point_a_on_foreground_boundary,
        point_b_on_foreground_boundary=candidate.point_b_on_foreground_boundary,
        point_a_source_layer=candidate.point_a_source_layer,
        point_b_source_layer=candidate.point_b_source_layer,
        internal_gap_count=candidate.internal_gap_count,
        max_internal_gap_px=candidate.max_internal_gap_px,
        mesh_outer_span_px=candidate.mesh_outer_span_px,
        bundle_outer_span_px=candidate.bundle_outer_span_px,
        formal_ab_span_px=candidate.formal_ab_span_px,
        virtual_envelope_span_px=candidate.virtual_envelope_span_px,
        candidate_line_is_debug_only=True
        if candidate.candidate_line_is_debug_only is None
        else candidate.candidate_line_is_debug_only,
        selected_line_reason=candidate.selected_line_reason,
        measurement_mode=candidate.measurement_mode,
        neighbor_line_support=candidate.neighbor_line_support,
    )


def _chord_debug(
    *,
    roi: RotatedRoi,
    boundary_margin_px: float,
    contour_point_count: int | None,
    pattern_model: str | None,
    measurement_mode: str | None,
    min_projection: float | None = None,
    max_projection: float | None = None,
    point_a: Point2D | None = None,
    point_b: Point2D | None = None,
    point_a_local: Point2D | None = None,
    point_b_local: Point2D | None = None,
    rejected_side: str | None = None,
    measurement_line_y: float | None = None,
    local_y_delta_px: float | None = None,
    parallel_error_px: float | None = None,
    chord_length_px: float | None = None,
    detected_pattern: str | None = None,
    object_interval_count: int | None = None,
    interval_count: int | None = None,
    selected_intervals: list[ObjectInterval] | None = None,
    raw_intervals: list[ObjectInterval] | None = None,
    bridged_intervals: list[ObjectInterval] | None = None,
    selected_valid_intervals: list[ObjectInterval] | None = None,
    leftmost_valid_interval: ObjectInterval | None = None,
    rightmost_valid_interval: ObjectInterval | None = None,
    formal_point_a_source_interval: ObjectInterval | None = None,
    formal_point_b_source_interval: ObjectInterval | None = None,
    point_a_on_foreground_boundary: bool | None = None,
    point_b_on_foreground_boundary: bool | None = None,
    point_a_source_layer: str | None = None,
    point_b_source_layer: str | None = None,
    internal_gap_count: int | None = None,
    max_internal_gap_px: float | None = None,
    mesh_outer_span_px: float | None = None,
    bundle_outer_span_px: float | None = None,
    formal_ab_span_px: float | None = None,
    virtual_envelope_span_px: float | None = None,
    candidate_line_is_debug_only: bool | None = None,
    selected_line_reason: str | None = None,
    neighbor_line_support: int | None = None,
) -> ContactDebug:
    return ContactDebug(
        contour_point_count=contour_point_count,
        min_local_projection=min_projection,
        max_local_projection=max_projection,
        roi_min_allowed_projection=-roi.width / 2.0 + boundary_margin_px,
        roi_max_allowed_projection=roi.width / 2.0 - boundary_margin_px,
        distance_to_left_roi_boundary_px=None
        if min_projection is None
        else min_projection + roi.width / 2.0,
        distance_to_right_roi_boundary_px=None
        if max_projection is None
        else roi.width / 2.0 - max_projection,
        rejected_side=rejected_side,
        rejected_candidate_point_a=point_a,
        rejected_candidate_point_b=point_b,
        point_a_local=point_a_local,
        point_b_local=point_b_local,
        measurement_line_y=measurement_line_y,
        local_y_delta_px=local_y_delta_px,
        parallel_error_px=parallel_error_px,
        chord_length_px=chord_length_px,
        pattern_model=pattern_model,
        detected_pattern=detected_pattern,
        object_interval_count=object_interval_count,
        interval_count=interval_count,
        selected_intervals=selected_intervals,
        raw_intervals=raw_intervals,
        bridged_intervals=bridged_intervals,
        selected_valid_intervals=selected_valid_intervals,
        leftmost_valid_interval=leftmost_valid_interval,
        rightmost_valid_interval=rightmost_valid_interval,
        formal_point_a_source_interval=formal_point_a_source_interval,
        formal_point_b_source_interval=formal_point_b_source_interval,
        point_a_on_foreground_boundary=point_a_on_foreground_boundary,
        point_b_on_foreground_boundary=point_b_on_foreground_boundary,
        point_a_source_layer=point_a_source_layer,
        point_b_source_layer=point_b_source_layer,
        internal_gap_count=internal_gap_count,
        max_internal_gap_px=max_internal_gap_px,
        mesh_outer_span_px=mesh_outer_span_px,
        bundle_outer_span_px=bundle_outer_span_px,
        formal_ab_span_px=formal_ab_span_px,
        virtual_envelope_span_px=virtual_envelope_span_px,
        candidate_line_is_debug_only=candidate_line_is_debug_only,
        selected_line_reason=selected_line_reason,
        measurement_mode=measurement_mode,
        neighbor_line_support=neighbor_line_support,
    )


def _support_index(
    projection: np.ndarray,
    perpendicular: np.ndarray,
    support_projection: float,
) -> int:
    tolerance = 0.5
    candidate_indices = np.flatnonzero(np.abs(projection - support_projection) <= tolerance)
    if candidate_indices.size == 0:
        return int(np.argmin(np.abs(projection - support_projection)))
    best_local = np.argmin(np.abs(perpendicular[candidate_indices]))
    return int(candidate_indices[best_local])


def _empty_contact_debug(roi: RotatedRoi, boundary_margin_px: float) -> ContactDebug:
    return ContactDebug(
        contour_point_count=None,
        min_local_projection=None,
        max_local_projection=None,
        roi_min_allowed_projection=-roi.width / 2.0 + boundary_margin_px,
        roi_max_allowed_projection=roi.width / 2.0 - boundary_margin_px,
        distance_to_left_roi_boundary_px=None,
        distance_to_right_roi_boundary_px=None,
        rejected_side=None,
        rejected_candidate_point_a=None,
        rejected_candidate_point_b=None,
    )


def _contact_debug(
    *,
    roi: RotatedRoi,
    boundary_margin_px: float,
    contour_point_count: int,
    min_projection: float,
    max_projection: float,
    point_a: Point2D | None,
    point_b: Point2D | None,
    rejected_side: str | None,
) -> ContactDebug:
    return ContactDebug(
        contour_point_count=contour_point_count,
        min_local_projection=min_projection,
        max_local_projection=max_projection,
        roi_min_allowed_projection=-roi.width / 2.0 + boundary_margin_px,
        roi_max_allowed_projection=roi.width / 2.0 - boundary_margin_px,
        distance_to_left_roi_boundary_px=min_projection + roi.width / 2.0,
        distance_to_right_roi_boundary_px=roi.width / 2.0 - max_projection,
        rejected_side=rejected_side,
        rejected_candidate_point_a=point_a,
        rejected_candidate_point_b=point_b,
    )


def _rejected_side(left_rejected: bool, right_rejected: bool) -> str | None:
    if left_rejected and right_rejected:
        return "both"
    if left_rejected:
        return "left"
    if right_rejected:
        return "right"
    return None
