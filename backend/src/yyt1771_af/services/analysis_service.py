from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from yyt1771_af.core.models import (
    AnalysisCurvePoint,
    AnalysisResponse,
    AnalysisResult,
    RunSample,
)
from yyt1771_af.core.statuses import AnalysisMethod, AnalysisStatus
from yyt1771_af.storage.run_store import RunArtifactStore, run_artifact_store

MIN_AF95_POINTS = 3
RECOVERY_TARGET_FRACTION = 0.95


@dataclass(frozen=True, slots=True)
class _SamplePartition:
    usable: list[RunSample]
    invalid_sample_count: int
    missing_temperature_count: int
    missing_distance_count: int


class AnalysisService:
    def __init__(self, *, store: RunArtifactStore) -> None:
        self._store = store

    def analyze_run(
        self,
        run_id: str,
        *,
        method: AnalysisMethod = AnalysisMethod.AF95_V1,
    ) -> AnalysisResponse:
        if method is not AnalysisMethod.AF95_V1:
            return AnalysisResponse(
                method=method,
                status=AnalysisStatus.INSUFFICIENT_DATA,
                curve=[],
                result=None,
                diagnostics={
                    "reason": "Only af95_v1 is implemented in this phase.",
                },
            )

        samples = [RunSample.model_validate(sample) for sample in self._store.read_samples(run_id)]
        partition = _partition_samples(samples)
        response = _analyze_af95(partition)
        self._store.write_analysis(run_id, response.model_dump(mode="json"))
        return response

    def get_analysis(self, run_id: str) -> AnalysisResponse:
        payload = self._store.read_analysis(run_id)
        if payload is None:
            raise KeyError(f"analysis for run {run_id} is not available")
        return AnalysisResponse.model_validate(payload)


def _partition_samples(samples: list[RunSample]) -> _SamplePartition:
    usable: list[RunSample] = []
    invalid_sample_count = 0
    missing_temperature_count = 0
    missing_distance_count = 0

    for sample in samples:
        distance_px = sample.detection.distance_px
        if not sample.detection.valid or distance_px is None:
            invalid_sample_count += 1
            missing_distance_count += 1
            continue
        if sample.temperature_c is None:
            invalid_sample_count += 1
            missing_temperature_count += 1
            continue
        usable.append(sample)

    return _SamplePartition(
        usable=usable,
        invalid_sample_count=invalid_sample_count,
        missing_temperature_count=missing_temperature_count,
        missing_distance_count=missing_distance_count,
    )


def _analyze_af95(partition: _SamplePartition) -> AnalysisResponse:
    usable = sorted(
        partition.usable,
        key=lambda sample: (
            sample.temperature_c if sample.temperature_c is not None else float("inf"),
            sample.timestamp_ms,
            sample.sample_index,
        ),
    )
    diagnostics: dict[str, Any] = _diagnostics(partition, valid_sample_count=len(usable))
    if not usable:
        return AnalysisResponse(
            method=AnalysisMethod.AF95_V1,
            status=AnalysisStatus.NO_VALID_SAMPLES,
            curve=[],
            result=None,
            diagnostics=diagnostics | {"reason": "No valid temperature-distance samples."},
        )

    curve = _curve_points(usable)
    if len(usable) < MIN_AF95_POINTS:
        return AnalysisResponse(
            method=AnalysisMethod.AF95_V1,
            status=AnalysisStatus.INSUFFICIENT_DATA,
            curve=curve,
            result=None,
            diagnostics=diagnostics
            | {"reason": f"Need at least {MIN_AF95_POINTS} valid temperature-distance samples."},
        )

    initial_distance = curve[0].distance_px
    final_distance = curve[-1].distance_px
    direction = final_distance - initial_distance
    if abs(direction) < 1e-9:
        return AnalysisResponse(
            method=AnalysisMethod.AF95_V1,
            status=AnalysisStatus.INSUFFICIENT_DATA,
            curve=curve,
            result=None,
            diagnostics=diagnostics | {"reason": "Distance change is too small for Af-95."},
        )

    curve = _curve_points(usable, initial_distance=initial_distance, direction=direction)
    af95_temperature = _interpolate_af95(curve)
    if af95_temperature is None:
        return AnalysisResponse(
            method=AnalysisMethod.AF95_V1,
            status=AnalysisStatus.UNSTABLE_CURVE,
            curve=curve,
            result=None,
            diagnostics=diagnostics | {"reason": "Curve never reaches 95% recovered fraction."},
        )

    distances = [point.distance_px for point in curve]
    temperatures = [point.temperature_c for point in curve]
    distance_span = max(distances) - min(distances)
    recovered_fraction = (
        0.0
        if distance_span <= 1e-9
        else min(1.0, abs(final_distance - initial_distance) / distance_span)
    )
    return AnalysisResponse(
        method=AnalysisMethod.AF95_V1,
        status=AnalysisStatus.OK,
        curve=curve,
        result=AnalysisResult(
            min_distance_px=min(distances),
            max_distance_px=max(distances),
            initial_distance_px=initial_distance,
            final_distance_px=final_distance,
            recovered_fraction=recovered_fraction,
            valid_sample_count=len(curve),
            invalid_sample_count=partition.invalid_sample_count,
            temperature_range=(min(temperatures), max(temperatures)),
            af95_temperature_c=round(af95_temperature, 6),
        ),
        diagnostics=diagnostics,
    )


def _curve_points(
    samples: list[RunSample],
    *,
    initial_distance: float | None = None,
    direction: float | None = None,
) -> list[AnalysisCurvePoint]:
    points: list[AnalysisCurvePoint] = []
    for sample in samples:
        assert sample.temperature_c is not None
        assert sample.detection.distance_px is not None
        distance_px = sample.detection.distance_px
        if initial_distance is None or direction is None or abs(direction) < 1e-9:
            recovered_fraction = 0.0
        else:
            recovered_fraction = (distance_px - initial_distance) / direction
        points.append(
            AnalysisCurvePoint(
                sample_index=sample.sample_index,
                timestamp_ms=sample.timestamp_ms,
                temperature_c=sample.temperature_c,
                distance_px=distance_px,
                recovered_fraction=max(0.0, min(1.0, recovered_fraction)),
            )
        )
    return points


def _interpolate_af95(curve: list[AnalysisCurvePoint]) -> float | None:
    previous = curve[0]
    if previous.recovered_fraction >= RECOVERY_TARGET_FRACTION:
        return previous.temperature_c

    for point in curve[1:]:
        if point.recovered_fraction < RECOVERY_TARGET_FRACTION:
            previous = point
            continue
        fraction_delta = point.recovered_fraction - previous.recovered_fraction
        if abs(fraction_delta) < 1e-9:
            return point.temperature_c
        interpolation_fraction = (
            RECOVERY_TARGET_FRACTION - previous.recovered_fraction
        ) / fraction_delta
        return (
            previous.temperature_c
            + (point.temperature_c - previous.temperature_c) * interpolation_fraction
        )
    return None


def _diagnostics(partition: _SamplePartition, *, valid_sample_count: int) -> dict[str, Any]:
    return {
        "valid_sample_count": valid_sample_count,
        "invalid_sample_count": partition.invalid_sample_count,
        "missing_temperature_count": partition.missing_temperature_count,
        "missing_distance_count": partition.missing_distance_count,
    }


analysis_service = AnalysisService(store=run_artifact_store)

__all__ = ["AnalysisMethod", "AnalysisService", "analysis_service"]
