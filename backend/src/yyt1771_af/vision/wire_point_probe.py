from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from yyt1771_af.core.models import (
    DetectionResult,
    FrameIdentity,
    Point2D,
    PointProbeResponse,
    RotatedRoi,
    SegmentationParams,
    WireComponentDiagnostics,
    WireStripDetectorParams,
)
from yyt1771_af.core.statuses import CoordinateSpace, TargetFamily
from yyt1771_af.vision.detection import detect_target
from yyt1771_af.vision.roi_ops import (
    acquisition_to_roi_local_point,
    rotated_roi_mask,
)
from yyt1771_af.vision.segmentation import (
    BinaryComponent,
    connected_components,
    segment_target_mask_layers_debug,
)
from yyt1771_af.vision.wire_filtering import WireForegroundAnalysis, analyze_wire_components


@dataclass(frozen=True, slots=True)
class WireDebugEvidence:
    detection: DetectionResult
    raw_foreground: np.ndarray
    morphology_foreground: np.ndarray
    wire_foreground: np.ndarray
    components: list[BinaryComponent]
    analysis: WireForegroundAnalysis


def wire_component_diagnostics(analysis: WireForegroundAnalysis) -> list[WireComponentDiagnostics]:
    return [
        WireComponentDiagnostics(
            component_id=metric.component_id,
            area_px=metric.area_px,
            area_ratio_in_roi=metric.area_ratio_in_roi,
            bbox=metric.bbox,
            aspect_ratio=metric.aspect_ratio,
            orientation_deg=metric.orientation_deg,
            orientation_deviation_deg=metric.orientation_deviation_deg,
            local_contrast=metric.local_contrast,
            wire_likeness_score=metric.wire_likeness_score,
            accepted=metric.accepted,
            reject_reason=metric.reject_reason,
        )
        for metric in analysis.metrics
    ]


def build_wire_debug_evidence(
    *,
    frame: np.ndarray,
    roi: RotatedRoi,
    segmentation: SegmentationParams,
    params: WireStripDetectorParams,
    debug_level: str = "full",
) -> WireDebugEvidence:
    roi_mask = rotated_roi_mask(frame.shape, roi)
    layers, _, _ = segment_target_mask_layers_debug(
        frame,
        roi_mask,
        segmentation,
        preferred_point_xy=(roi.center_x, roi.center_y),
    )
    components = connected_components(
        layers.morphology_foreground,
        segmentation.min_component_area_px,
    )
    analysis = analyze_wire_components(
        image=frame,
        roi=roi,
        roi_mask=roi_mask,
        foreground=layers.morphology_foreground,
        components=components,
        params=params,
    )
    detection = detect_target(
        frame=frame,
        roi=roi,
        target_family=TargetFamily.WIRE_STRIP,
        segmentation=segmentation,
        params=params,
        debug_level=debug_level,  # type: ignore[arg-type]
    )
    return WireDebugEvidence(
        detection=detection,
        raw_foreground=layers.raw_foreground,
        morphology_foreground=layers.morphology_foreground,
        wire_foreground=analysis.wire_foreground,
        components=components,
        analysis=analysis,
    )


def probe_wire_point(
    *,
    frame: np.ndarray,
    roi: RotatedRoi,
    segmentation: SegmentationParams,
    params: WireStripDetectorParams,
    point: Point2D,
    identity: FrameIdentity,
) -> PointProbeResponse:
    evidence = build_wire_debug_evidence(
        frame=frame,
        roi=roi,
        segmentation=segmentation,
        params=params,
        debug_level="full",
    )
    height, width = frame.shape[:2]
    px = int(round(point.x))
    py = int(round(point.y))
    in_frame = 0 <= px < width and 0 <= py < height
    pixel_value = int(frame[py, px]) if in_frame else None
    local = acquisition_to_roi_local_point(roi, point)
    inside_roi = bool(abs(local.x) <= roi.width / 2.0 and abs(local.y) <= roi.height / 2.0)
    raw_foreground = _mask_hit(evidence.raw_foreground, px, py)
    morphology_foreground = _mask_hit(evidence.morphology_foreground, px, py)
    wire_foreground = _mask_hit(evidence.wire_foreground, px, py)
    component_id = _component_id_at(evidence.components, px, py)
    metric = (
        next(
            (item for item in evidence.analysis.metrics if item.component_id == component_id),
            None,
        )
        if component_id is not None
        else None
    )
    selected_interval_id, selected_interval = _interval_hit(
        evidence.detection.diagnostics.selected_valid_intervals,
        local.x,
        local.y,
        "selected_valid",
    )
    rejected_interval_id, rejected_interval = _interval_hit(
        evidence.detection.diagnostics.rejected_intervals,
        local.x,
        local.y,
        "rejected",
    )
    rejected_remote_id, rejected_remote_interval = _interval_hit(
        evidence.detection.diagnostics.rejected_remote_intervals,
        local.x,
        local.y,
        "rejected_remote",
    )
    source_interval_id = _source_interval_id(evidence.detection, local.x, local.y)
    would_be_source = source_interval_id is not None
    interval_id = selected_interval_id or rejected_interval_id or rejected_remote_id
    interval_reject_reason = None
    if rejected_remote_interval is not None:
        interval_reject_reason = rejected_remote_interval.reject_reason
    elif rejected_interval is not None:
        interval_reject_reason = rejected_interval.reject_reason
    return PointProbeResponse(
        frame_identity=identity,
        x=point.x,
        y=point.y,
        coordinate_space=CoordinateSpace.ACQUISITION,
        pixel_value=pixel_value,
        inside_roi=inside_roi,
        raw_foreground=raw_foreground,
        morphology_foreground=morphology_foreground,
        wire_foreground=wire_foreground,
        component_id=component_id,
        component_accepted=metric.accepted if metric is not None else None,
        component_reject_reason=metric.reject_reason if metric is not None else None,
        interval_id=interval_id,
        selected_valid_interval=selected_interval is not None,
        rejected_interval=rejected_interval is not None,
        rejected_remote_interval=rejected_remote_interval is not None,
        reject_reason=interval_reject_reason
        or (metric.reject_reason if metric is not None else None),
        source_interval_id=source_interval_id,
        would_be_ab_source=would_be_source,
    )


def _mask_hit(mask: np.ndarray, px: int, py: int) -> bool:
    return bool(0 <= py < mask.shape[0] and 0 <= px < mask.shape[1] and mask[py, px])


def _component_id_at(components: list[BinaryComponent], px: int, py: int) -> int | None:
    for component_id, component in enumerate(components):
        if _mask_hit(component.mask, px, py):
            return component_id
    return None


def _interval_hit(
    intervals: list[object] | None,
    local_x: float,
    local_y: float,
    prefix: str,
) -> tuple[str | None, object | None]:
    if not intervals:
        return None, None
    for index, interval in enumerate(intervals):
        line_y = getattr(interval, "line_y", None)
        if isinstance(line_y, int | float) and abs(local_y - float(line_y)) > 1.0:
            continue
        start = float(interval.start_local_x)
        end = float(interval.end_local_x)
        if start - 0.5 <= local_x <= end + 0.5:
            return f"{prefix}:{index}", interval
    return None, None


def _source_interval_id(detection: DetectionResult, local_x: float, local_y: float) -> str | None:
    candidates = (
        ("point_a_source_interval", detection.diagnostics.point_a_source_interval),
        ("point_b_source_interval", detection.diagnostics.point_b_source_interval),
        ("formal_point_a_source_interval", detection.diagnostics.formal_point_a_source_interval),
        ("formal_point_b_source_interval", detection.diagnostics.formal_point_b_source_interval),
    )
    for name, interval in candidates:
        _, hit = _interval_hit([interval] if interval is not None else None, local_x, local_y, name)
        if hit is not None:
            return name
    return None
