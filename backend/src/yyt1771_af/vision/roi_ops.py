from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from yyt1771_af.core.geometry import euclidean_distance, roi_inside_frame, roi_measurement_direction
from yyt1771_af.core.models import (
    ComponentBBox,
    DetectionDiagnostics,
    DetectionResult,
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


@dataclass(frozen=True, slots=True)
class ContactDebug:
    contour_point_count: int | None
    min_local_projection: float | None
    max_local_projection: float | None
    roi_min_allowed_projection: float | None
    roi_max_allowed_projection: float | None
    distance_to_left_roi_boundary_px: float | None
    distance_to_right_roi_boundary_px: float | None
    rejected_side: str | None
    rejected_candidate_point_a: Point2D | None
    rejected_candidate_point_b: Point2D | None


@dataclass(frozen=True, slots=True)
class ContactRejection:
    status: DetectionStatus
    debug: ContactDebug


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
