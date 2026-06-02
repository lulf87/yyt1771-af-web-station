from __future__ import annotations

from yyt1771_af.core.geometry import euclidean_distance
from yyt1771_af.core.models import DetectionResult
from yyt1771_af.core.statuses import DetectionStatus


def record_previous_frame_diagnostics(
    detection: DetectionResult,
    previous: DetectionResult,
    *,
    max_jump_px: float | None = None,
    reject_on_jump: bool = False,
) -> None:
    """Attach previous-frame jump metrics and optionally reject excessive jumps."""
    if not detection.valid or not previous.valid:
        return
    if detection.point_a is None or detection.point_b is None:
        return
    if previous.point_a is None or previous.point_b is None:
        return
    detection.diagnostics.previous_measurement_line_y = previous.diagnostics.measurement_line_y
    if (
        detection.diagnostics.measurement_line_y is not None
        and previous.diagnostics.measurement_line_y is not None
    ):
        line_y_delta = abs(
            detection.diagnostics.measurement_line_y - previous.diagnostics.measurement_line_y
        )
        detection.diagnostics.line_y_delta_from_previous = line_y_delta
        detection.diagnostics.measurement_line_y_delta_from_previous = line_y_delta
    if detection.distance_px is not None and previous.distance_px is not None:
        distance_jump = abs(detection.distance_px - previous.distance_px)
        detection.diagnostics.distance_jump_from_previous = distance_jump
        detection.diagnostics.abs_distance_jump_from_previous = distance_jump
    detection.diagnostics.point_a_jump_from_previous = euclidean_distance(
        previous.point_a,
        detection.point_a,
    )
    detection.diagnostics.point_b_jump_from_previous = euclidean_distance(
        previous.point_b,
        detection.point_b,
    )
    jumps = [
        value
        for value in (
            detection.diagnostics.distance_jump_from_previous,
            detection.diagnostics.point_a_jump_from_previous,
            detection.diagnostics.point_b_jump_from_previous,
        )
        if value is not None
    ]
    if max_jump_px is not None and jumps and max(jumps) > max_jump_px:
        detection.diagnostics.is_top_jump_candidate = True
        detection.diagnostics.jump_warning = (
            f"Frame-to-frame jump exceeds configured threshold {max_jump_px:.2f}px."
        )
        if reject_on_jump:
            detection.diagnostics.rejected_candidate_point_a = detection.point_a
            detection.diagnostics.rejected_candidate_point_b = detection.point_b
            detection.diagnostics.message = detection.diagnostics.jump_warning
            detection.status = DetectionStatus.JUMP_EXCEEDS_LIMIT
            detection.valid = False
            detection.point_a = None
            detection.point_b = None
            detection.distance_px = None
    elif max_jump_px is not None:
        detection.diagnostics.is_top_jump_candidate = False
