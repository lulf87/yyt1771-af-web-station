from __future__ import annotations

from dataclasses import dataclass

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
    selected_intervals: list[ObjectInterval] | None = None
    measurement_mode: str | None = None


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
    selected_intervals: list[ObjectInterval] | None = None
    measurement_mode: str | None = None


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
    contour_point_count: int
    distance_to_left_roi_boundary_px: float
    distance_to_right_roi_boundary_px: float
    rejected_side: str | None = None
    measurement_mode: str | None = None


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


def select_roi_local_chord_contacts_debug(
    mask: np.ndarray,
    roi: RotatedRoi,
    *,
    pattern_model: str,
    boundary_margin_px: float,
    reject_contact_on_roi_boundary: bool,
    measurement_mode: str | None = None,
    line_step_px: float = 1.0,
) -> ContactSelection | ContactRejection:
    foreground = np.asarray(mask, dtype=bool)
    edge_mask = contour_mask(foreground)
    contour_count = int(np.count_nonzero(edge_mask))
    if not np.any(foreground):
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

    candidates: list[_LineCandidate] = []
    rejected_boundary: list[_LineCandidate] = []
    mismatched: list[_LineCandidate] = []
    for local_y in _measurement_line_values(roi, line_step_px):
        line_mask, local_x_values = _sample_mask_line(foreground, roi, local_y)
        intervals = _line_intervals(line_mask, local_x_values, local_y)
        if not intervals:
            continue
        candidate = _build_line_candidate(
            roi=roi,
            local_y=local_y,
            intervals=intervals,
            pattern_model=pattern_model,
            measurement_mode=measurement_mode,
            contour_point_count=contour_count,
        )
        if candidate is None:
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
        candidate = _best_line_candidate(candidates)
        if global_margins is not None and reject_contact_on_roi_boundary:
            left_rejected = global_margins.left_margin_px <= boundary_margin_px
            right_rejected = global_margins.right_margin_px <= boundary_margin_px
            if left_rejected or right_rejected:
                candidate = (
                    _best_line_candidate(rejected_boundary) if rejected_boundary else candidate
                )
                return ContactRejection(
                    status=DetectionStatus.CALIPER_CONTACT_ON_ROI_BOUNDARY,
                    debug=_candidate_to_debug(
                        _replace_rejected_side(
                            candidate,
                            _rejected_side(left_rejected, right_rejected),
                        ),
                        roi,
                        boundary_margin_px,
                    ),
                )
        return _candidate_to_selection(candidate)
    if rejected_boundary:
        candidate = _best_line_candidate(rejected_boundary)
        return ContactRejection(
            status=DetectionStatus.CALIPER_CONTACT_ON_ROI_BOUNDARY,
            debug=_candidate_to_debug(candidate, roi, boundary_margin_px),
        )
    if mismatched:
        candidate = _best_line_candidate(mismatched)
        return ContactRejection(
            status=DetectionStatus.OBJECT_INTERVAL_COUNT_MISMATCH,
            debug=_candidate_to_debug(candidate, roi, boundary_margin_px),
        )
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
            selected_intervals=selection.selected_intervals,
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
        contour_point_count=contour_point_count,
        distance_to_left_roi_boundary_px=float(point_a_x + roi.width / 2.0),
        distance_to_right_roi_boundary_px=float(roi.width / 2.0 - point_b_x),
        measurement_mode=measurement_mode,
    )


def _expected_interval_count(pattern_model: str) -> int | None:
    if pattern_model == "blank_object_blank":
        return 1
    if pattern_model == "blank_object_blank_object_blank":
        return 2
    return None


def _detected_pattern(interval_count: int) -> str:
    if interval_count == 1:
        return "blank_object_blank"
    if interval_count == 2:
        return "blank_object_blank_object_blank"
    if interval_count > 2:
        return "multiple_object_intervals"
    return "blank"


def _best_line_candidate(candidates: list[_LineCandidate]) -> _LineCandidate:
    return max(
        candidates,
        key=lambda candidate: (candidate.chord_length_px, -abs(candidate.measurement_line_y)),
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
        contour_point_count=candidate.contour_point_count,
        distance_to_left_roi_boundary_px=candidate.distance_to_left_roi_boundary_px,
        distance_to_right_roi_boundary_px=candidate.distance_to_right_roi_boundary_px,
        rejected_side=rejected_side,
        measurement_mode=candidate.measurement_mode,
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
        selected_intervals=candidate.intervals,
        measurement_mode=candidate.measurement_mode,
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
        selected_intervals=candidate.intervals,
        measurement_mode=candidate.measurement_mode,
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
    selected_intervals: list[ObjectInterval] | None = None,
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
        selected_intervals=selected_intervals,
        measurement_mode=measurement_mode,
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
