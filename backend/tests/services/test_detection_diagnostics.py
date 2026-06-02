from __future__ import annotations

from yyt1771_af.core.models import DetectionDiagnostics, DetectionResult, Point2D
from yyt1771_af.core.statuses import DetectionStatus, DetectorKind, TargetFamily
from yyt1771_af.services.detection_diagnostics import record_previous_frame_diagnostics


def _valid_wire_detection(*, point_b_x: float, distance_px: float) -> DetectionResult:
    return DetectionResult(
        status=DetectionStatus.OK,
        valid=True,
        point_a=Point2D(x=10.0, y=20.0),
        point_b=Point2D(x=point_b_x, y=20.0),
        distance_px=distance_px,
        quality=0.92,
        target_family=TargetFamily.WIRE_STRIP,
        diagnostics=DetectionDiagnostics(
            detector=DetectorKind.WIRE_STRIP_DETECTOR,
            measurement_line_y=0.0,
        ),
    )


def test_record_previous_frame_diagnostics_can_reject_jump_exceeds_limit() -> None:
    previous = _valid_wire_detection(point_b_x=150.0, distance_px=140.0)
    current = _valid_wire_detection(point_b_x=185.0, distance_px=175.0)

    record_previous_frame_diagnostics(
        current,
        previous,
        max_jump_px=20.0,
        reject_on_jump=True,
    )

    assert current.valid is False
    assert current.status is DetectionStatus.JUMP_EXCEEDS_LIMIT
    assert current.point_a is None
    assert current.point_b is None
    assert current.distance_px is None
    assert current.diagnostics.distance_jump_from_previous == 35.0
    assert current.diagnostics.is_top_jump_candidate is True
    assert current.diagnostics.jump_warning is not None
