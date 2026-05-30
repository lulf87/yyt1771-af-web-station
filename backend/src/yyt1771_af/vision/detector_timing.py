from __future__ import annotations

import time
from collections.abc import Mapping

from yyt1771_af.core.models import DetectionDiagnostics, DetectionResult


def elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 3)


def attach_detector_timings(
    result: DetectionResult,
    timings_ms: Mapping[str, float],
    *,
    detector_start: float,
) -> DetectionResult:
    payload = result.diagnostics.model_dump(mode="python")
    payload.update(
        {key: round(float(value), 3) for key, value in timings_ms.items() if value is not None}
    )
    payload["detector_total_ms"] = elapsed_ms(detector_start)
    result.diagnostics = DetectionDiagnostics.model_validate(payload)
    return result
