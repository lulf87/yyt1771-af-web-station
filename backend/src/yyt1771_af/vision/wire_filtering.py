"""Component-level wire-likeness analysis for ``WireStripDetector``.

This module evaluates each connected foreground component inside the ROI and
decides whether it looks like part of a wire bundle or like a non-target broad
background blob / low-contrast patch. It is pure NumPy and has no FastAPI,
OpenCV, hardware, or filesystem dependencies.

Phase 1 uses the analysis only for diagnostics and overlays; the formal A/B
selection still runs on the raw segmentation foreground. Phase 2 feeds
``WireForegroundAnalysis.wire_foreground`` into the chord selection so that
background blobs can no longer become wire intervals.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from yyt1771_af.core.geometry import roi_measurement_direction
from yyt1771_af.core.models import ComponentBBox, RotatedRoi, WireStripDetectorParams
from yyt1771_af.vision.segmentation import BinaryComponent, binary_dilate

# Wire-likeness defaults. The detector passes a confirmed
# ``WireStripDetectorParams`` snapshot at run time; these constants remain only
# as fallback defaults for direct unit usage.
MIN_WIRE_ASPECT_RATIO = 1.8
BROAD_BLOB_AREA_RATIO = 0.22
BROAD_BLOB_MAX_ASPECT_RATIO = 1.8
MIN_LOCAL_CONTRAST = 6.0
LOCAL_CONTRAST_BAND_PX = 4

# wire_likeness_score normalisation targets.
_TARGET_ASPECT_RATIO = 4.0
_TARGET_LOCAL_CONTRAST = 40.0
_GOOD_AREA_RATIO = 0.10
_MAX_AREA_RATIO = 0.45


@dataclass(frozen=True, slots=True)
class WireComponentMetric:
    component_id: int
    area_px: int
    area_ratio_in_roi: float
    bbox: ComponentBBox
    aspect_ratio: float
    orientation_deg: float
    orientation_deviation_deg: float
    local_contrast: float
    wire_likeness_score: float
    accepted: bool
    reject_reason: str | None


@dataclass(frozen=True, slots=True)
class WireForegroundAnalysis:
    wire_foreground: np.ndarray
    metrics: list[WireComponentMetric]
    broad_blob_rejection_count: int
    broad_blob_area_ratio: float
    primary_aspect_ratio: float | None
    primary_orientation_deg: float | None
    primary_wire_likeness_score: float | None
    accepted_component_count: int
    rejected_component_count: int


def analyze_wire_components(
    *,
    image: np.ndarray,
    roi: RotatedRoi,
    roi_mask: np.ndarray,
    foreground: np.ndarray,
    components: list[BinaryComponent],
    params: WireStripDetectorParams | None = None,
) -> WireForegroundAnalysis:
    params = params or WireStripDetectorParams()
    gray = np.asarray(image)
    roi_area = max(1, int(np.count_nonzero(roi_mask)))
    foreground_bool = np.asarray(foreground, dtype=bool)
    unit_x, unit_y = roi_measurement_direction(roi.angle_deg)
    perp_x, perp_y = -unit_y, unit_x

    metrics: list[WireComponentMetric] = []
    wire_foreground = np.zeros(foreground_bool.shape, dtype=bool)
    broad_blob_count = 0
    broad_blob_area_ratio = 0.0
    accepted_count = 0
    rejected_count = 0
    primary: tuple[float, WireComponentMetric, BinaryComponent] | None = None

    for component_id, component in enumerate(components):
        metric = _component_metric(
            component_id=component_id,
            component=component,
            gray=gray,
            roi=roi,
            roi_mask=roi_mask,
            foreground=foreground_bool,
            roi_area=roi_area,
            unit_x=unit_x,
            unit_y=unit_y,
            perp_x=perp_x,
            perp_y=perp_y,
            params=params,
        )
        metrics.append(metric)
        if metric.accepted:
            wire_foreground |= component.mask
            accepted_count += 1
            score_key = metric.wire_likeness_score
            if primary is None or score_key > primary[0]:
                primary = (score_key, metric, component)
        else:
            rejected_count += 1
            if metric.reject_reason == "broad_blob":
                broad_blob_count += 1
                broad_blob_area_ratio = max(broad_blob_area_ratio, metric.area_ratio_in_roi)

    primary_metric = primary[1] if primary is not None else None
    return WireForegroundAnalysis(
        wire_foreground=wire_foreground,
        metrics=metrics,
        broad_blob_rejection_count=broad_blob_count,
        broad_blob_area_ratio=broad_blob_area_ratio,
        primary_aspect_ratio=primary_metric.aspect_ratio if primary_metric else None,
        primary_orientation_deg=primary_metric.orientation_deg if primary_metric else None,
        primary_wire_likeness_score=primary_metric.wire_likeness_score if primary_metric else None,
        accepted_component_count=accepted_count,
        rejected_component_count=rejected_count,
    )


def _component_metric(
    *,
    component_id: int,
    component: BinaryComponent,
    gray: np.ndarray,
    roi: RotatedRoi,
    roi_mask: np.ndarray,
    foreground: np.ndarray,
    roi_area: int,
    unit_x: float,
    unit_y: float,
    perp_x: float,
    perp_y: float,
    params: WireStripDetectorParams,
) -> WireComponentMetric:
    coords = component.coordinates_yx
    area_px = int(coords.shape[0])
    area_ratio = float(area_px / roi_area)

    centered_x = coords[:, 1].astype(np.float64) - roi.center_x
    centered_y = coords[:, 0].astype(np.float64) - roi.center_y
    local_x = centered_x * unit_x + centered_y * unit_y
    local_y = centered_x * perp_x + centered_y * perp_y
    aspect_ratio, orientation_deg = _pca_shape(local_x, local_y)
    orientation_deviation = orientation_deg if params.enable_orientation_scoring else 0.0
    local_contrast = _local_contrast(
        component=component,
        gray=gray,
        roi_mask=roi_mask,
        foreground=foreground,
    )
    wire_likeness = _wire_likeness_score(
        aspect_ratio=aspect_ratio,
        local_contrast=local_contrast,
        area_ratio=area_ratio,
    )
    accepted, reject_reason = _classify(
        area_px=area_px,
        aspect_ratio=aspect_ratio,
        area_ratio=area_ratio,
        local_contrast=local_contrast,
        wire_likeness_score=wire_likeness,
        params=params,
    )
    return WireComponentMetric(
        component_id=component_id,
        area_px=area_px,
        area_ratio_in_roi=round(area_ratio, 6),
        bbox=_component_bbox(component),
        aspect_ratio=round(aspect_ratio, 4),
        orientation_deg=round(orientation_deg, 4),
        orientation_deviation_deg=round(orientation_deviation, 4),
        local_contrast=round(local_contrast, 4),
        wire_likeness_score=round(wire_likeness, 4),
        accepted=accepted,
        reject_reason=reject_reason,
    )


def _pca_shape(local_x: np.ndarray, local_y: np.ndarray) -> tuple[float, float]:
    if local_x.size < 2:
        return 1.0, 0.0
    coords = np.column_stack((local_x, local_y))
    coords = coords - coords.mean(axis=0)
    covariance = np.cov(coords, rowvar=False)
    if not np.all(np.isfinite(covariance)):
        return 1.0, 0.0
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    eigenvalues = np.clip(eigenvalues, 0.0, None)
    major_index = int(np.argmax(eigenvalues))
    minor_index = 1 - major_index
    major_std = math.sqrt(float(eigenvalues[major_index]))
    minor_std = math.sqrt(float(eigenvalues[minor_index]))
    aspect_ratio = major_std / minor_std if minor_std > 1e-6 else 999.0
    major_vector = eigenvectors[:, major_index]
    # Orientation relative to the ROI measurement x-axis, folded to [0, 90].
    angle = math.degrees(math.atan2(abs(float(major_vector[1])), abs(float(major_vector[0]))))
    return min(aspect_ratio, 999.0), angle


def _local_contrast(
    *,
    component: BinaryComponent,
    gray: np.ndarray,
    roi_mask: np.ndarray,
    foreground: np.ndarray,
) -> float:
    coords = component.coordinates_yx
    if coords.size == 0:
        return 0.0
    pad = LOCAL_CONTRAST_BAND_PX
    y0 = max(0, int(np.min(coords[:, 0])) - pad)
    y1 = min(gray.shape[0], int(np.max(coords[:, 0])) + pad + 1)
    x0 = max(0, int(np.min(coords[:, 1])) - pad)
    x1 = min(gray.shape[1], int(np.max(coords[:, 1])) + pad + 1)
    component_window = component.mask[y0:y1, x0:x1]
    gray_window = gray[y0:y1, x0:x1]
    component_values = gray_window[component_window]
    if component_values.size == 0:
        return 0.0
    dilated = binary_dilate(component_window, 2 * LOCAL_CONTRAST_BAND_PX + 1)
    band = dilated & roi_mask[y0:y1, x0:x1] & ~foreground[y0:y1, x0:x1]
    band_values = gray_window[band]
    if band_values.size == 0:
        return 0.0
    return float(np.mean(band_values) - np.mean(component_values))


def _wire_likeness_score(
    *,
    aspect_ratio: float,
    local_contrast: float,
    area_ratio: float,
) -> float:
    slender_score = _clip01((aspect_ratio - 1.0) / (_TARGET_ASPECT_RATIO - 1.0))
    contrast_score = _clip01(local_contrast / _TARGET_LOCAL_CONTRAST)
    if area_ratio <= _GOOD_AREA_RATIO:
        area_score = 1.0
    else:
        area_score = _clip01(
            1.0 - (area_ratio - _GOOD_AREA_RATIO) / (_MAX_AREA_RATIO - _GOOD_AREA_RATIO)
        )
    return 0.4 * slender_score + 0.4 * contrast_score + 0.2 * area_score


def _classify(
    *,
    area_px: int,
    aspect_ratio: float,
    area_ratio: float,
    local_contrast: float,
    wire_likeness_score: float,
    params: WireStripDetectorParams,
) -> tuple[bool, str | None]:
    min_component_area = params.min_component_area_px
    if min_component_area is not None and area_px < min_component_area:
        return False, "component_too_small"
    if (
        params.enable_broad_blob_rejection
        and area_ratio >= params.max_broad_blob_area_ratio
        and aspect_ratio < params.broad_blob_max_aspect_ratio
    ):
        return False, "broad_blob"
    if params.enable_broad_blob_rejection and area_ratio > params.max_component_area_ratio:
        return False, "component_too_large"
    if params.enable_local_contrast_filter and local_contrast < params.min_local_contrast_score:
        return False, "low_contrast"
    if wire_likeness_score < params.min_wire_likeness_score:
        return False, "low_wire_likeness"
    return True, None


def _clip01(value: float) -> float:
    return float(min(1.0, max(0.0, value)))


def _component_bbox(component: BinaryComponent) -> ComponentBBox:
    yx = component.coordinates_yx
    return ComponentBBox(
        min_x=int(np.min(yx[:, 1])),
        min_y=int(np.min(yx[:, 0])),
        max_x=int(np.max(yx[:, 1])),
        max_y=int(np.max(yx[:, 0])),
    )
