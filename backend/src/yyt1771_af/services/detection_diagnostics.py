from __future__ import annotations

from yyt1771_af.core.geometry import euclidean_distance
from yyt1771_af.core.models import DetectionResult


def record_previous_frame_diagnostics(
    detection: DetectionResult,
    previous: DetectionResult,
) -> None:
    """Attach previous-frame jump metrics for analysis only; never changes formal A/B."""
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
        detection.diagnostics.line_y_delta_from_previous = abs(
            detection.diagnostics.measurement_line_y - previous.diagnostics.measurement_line_y
        )
    if detection.distance_px is not None and previous.distance_px is not None:
        detection.diagnostics.distance_jump_from_previous = abs(
            detection.distance_px - previous.distance_px
        )
    detection.diagnostics.point_a_jump_from_previous = euclidean_distance(
        previous.point_a,
        detection.point_a,
    )
    detection.diagnostics.point_b_jump_from_previous = euclidean_distance(
        previous.point_b,
        detection.point_b,
    )
