from pathlib import Path

import pytest
from yyt1771_af.core.models import (
    DetectionDiagnostics,
    DetectionResult,
    Point2D,
    RunSample,
)
from yyt1771_af.core.statuses import (
    AnalysisStatus,
    DetectionStatus,
    DetectorKind,
    TargetFamily,
    TemperatureStatus,
)
from yyt1771_af.services.analysis_service import AnalysisMethod, AnalysisService
from yyt1771_af.storage.run_store import RunArtifactStore


def test_af95_analysis_for_synthetic_monotonic_recovery_curve(tmp_path: Path) -> None:
    store = _store_with_samples(
        tmp_path,
        "run_monotonic",
        [
            _valid_sample(0, temperature_c=0.0, distance_px=100.0),
            _valid_sample(1, temperature_c=10.0, distance_px=70.0),
            _valid_sample(2, temperature_c=20.0, distance_px=40.0),
            _valid_sample(3, temperature_c=30.0, distance_px=10.0),
            _valid_sample(4, temperature_c=40.0, distance_px=0.0),
        ],
    )

    result = AnalysisService(store=store).analyze_run("run_monotonic")

    assert result.method is AnalysisMethod.AF95_V1
    assert result.status is AnalysisStatus.OK
    assert result.result is not None
    assert result.result.min_distance_px == 0.0
    assert result.result.max_distance_px == 100.0
    assert result.result.initial_distance_px == 100.0
    assert result.result.final_distance_px == 0.0
    assert result.result.recovered_fraction == 1.0
    assert result.result.valid_sample_count == 5
    assert result.result.invalid_sample_count == 0
    assert result.result.temperature_range == (0.0, 40.0)
    assert result.result.af95_temperature_c == pytest.approx(35.0)
    assert len(result.curve) == 5


def test_af95_analysis_for_noisy_recovery_curve(tmp_path: Path) -> None:
    store = _store_with_samples(
        tmp_path,
        "run_noisy",
        [
            _valid_sample(0, temperature_c=0.0, distance_px=100.0),
            _valid_sample(1, temperature_c=10.0, distance_px=82.0),
            _valid_sample(2, temperature_c=20.0, distance_px=86.0),
            _valid_sample(3, temperature_c=30.0, distance_px=58.0),
            _valid_sample(4, temperature_c=40.0, distance_px=35.0),
            _valid_sample(5, temperature_c=50.0, distance_px=18.0),
            _valid_sample(6, temperature_c=60.0, distance_px=2.0),
        ],
    )

    result = AnalysisService(store=store).analyze_run("run_noisy")

    assert result.status is AnalysisStatus.OK
    assert result.result is not None
    assert 56.5 <= result.result.af95_temperature_c <= 57.5
    assert result.result.valid_sample_count == 7


def test_af95_analysis_returns_insufficient_data_for_too_few_points(
    tmp_path: Path,
) -> None:
    store = _store_with_samples(
        tmp_path,
        "run_short",
        [
            _valid_sample(0, temperature_c=0.0, distance_px=100.0),
            _valid_sample(1, temperature_c=10.0, distance_px=90.0),
        ],
    )

    result = AnalysisService(store=store).analyze_run("run_short")

    assert result.status is AnalysisStatus.INSUFFICIENT_DATA
    assert result.result is None
    assert result.diagnostics["valid_sample_count"] == 2


def test_analysis_filters_invalid_samples_without_changing_raw_jsonl(tmp_path: Path) -> None:
    samples = [
        _valid_sample(0, temperature_c=0.0, distance_px=100.0),
        _invalid_sample(1, temperature_c=10.0),
        _valid_sample(2, temperature_c=20.0, distance_px=50.0),
        _invalid_sample(3, temperature_c=30.0),
        _valid_sample(4, temperature_c=40.0, distance_px=0.0),
    ]
    store = _store_with_samples(tmp_path, "run_mixed", samples)
    raw_before = (tmp_path / "run_mixed" / "samples.jsonl").read_text(encoding="utf-8")

    result = AnalysisService(store=store).analyze_run("run_mixed")

    raw_after = (tmp_path / "run_mixed" / "samples.jsonl").read_text(encoding="utf-8")
    assert raw_after == raw_before
    assert result.status is AnalysisStatus.OK
    assert result.result is not None
    assert result.result.valid_sample_count == 3
    assert result.result.invalid_sample_count == 2
    assert [point.sample_index for point in result.curve] == [0, 2, 4]


def test_analysis_marks_missing_temperature_as_excluded_sample(tmp_path: Path) -> None:
    store = _store_with_samples(
        tmp_path,
        "run_missing_temperature",
        [
            _valid_sample(0, temperature_c=0.0, distance_px=100.0),
            _valid_sample(1, temperature_c=None, distance_px=80.0),
            _valid_sample(2, temperature_c=20.0, distance_px=60.0),
        ],
    )

    result = AnalysisService(store=store).analyze_run("run_missing_temperature")

    assert result.status is AnalysisStatus.INSUFFICIENT_DATA
    assert result.result is None
    assert result.diagnostics["missing_temperature_count"] == 1
    assert result.diagnostics["invalid_sample_count"] == 1


def test_analysis_returns_no_valid_samples_when_all_samples_are_invalid(
    tmp_path: Path,
) -> None:
    store = _store_with_samples(
        tmp_path,
        "run_invalid",
        [
            _invalid_sample(0, temperature_c=0.0),
            _invalid_sample(1, temperature_c=10.0),
            _valid_sample(2, temperature_c=None, distance_px=80.0),
        ],
    )

    result = AnalysisService(store=store).analyze_run("run_invalid")

    assert result.status is AnalysisStatus.NO_VALID_SAMPLES
    assert result.result is None
    assert result.diagnostics["invalid_sample_count"] == 3


def _store_with_samples(
    root: Path,
    run_id: str,
    samples: list[RunSample],
) -> RunArtifactStore:
    store = RunArtifactStore(root)
    store.create_run_dir(run_id)
    for sample in samples:
        store.append_sample(sample.model_copy(update={"run_id": run_id}))
    return store


def _valid_sample(
    sample_index: int,
    *,
    temperature_c: float | None,
    distance_px: float,
) -> RunSample:
    return RunSample(
        run_id="run",
        sample_index=sample_index,
        timestamp_ms=sample_index * 1000,
        temperature_c=temperature_c,
        temperature_status=(
            TemperatureStatus.OK if temperature_c is not None else TemperatureStatus.UNAVAILABLE
        ),
        detection=DetectionResult(
            status=DetectionStatus.OK,
            valid=True,
            point_a=Point2D(x=0.0, y=0.0),
            point_b=Point2D(x=distance_px, y=0.0),
            distance_px=distance_px,
            quality=0.9,
            target_family=TargetFamily.BALLOON_ENVELOPE,
            diagnostics=DetectionDiagnostics(detector=DetectorKind.BALLOON_ENVELOPE_DETECTOR),
        ),
    )


def _invalid_sample(sample_index: int, *, temperature_c: float | None) -> RunSample:
    return RunSample(
        run_id="run",
        sample_index=sample_index,
        timestamp_ms=sample_index * 1000,
        temperature_c=temperature_c,
        temperature_status=(
            TemperatureStatus.OK if temperature_c is not None else TemperatureStatus.UNAVAILABLE
        ),
        detection=DetectionResult(
            status=DetectionStatus.LOW_CONTRAST,
            valid=False,
            point_a=None,
            point_b=None,
            distance_px=None,
            quality=0.0,
            target_family=TargetFamily.BALLOON_ENVELOPE,
            diagnostics=DetectionDiagnostics(detector=DetectorKind.BALLOON_ENVELOPE_DETECTOR),
        ),
    )
