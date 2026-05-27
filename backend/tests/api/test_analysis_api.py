import json
from pathlib import Path

from fastapi.testclient import TestClient
from yyt1771_af.main import app


def test_run_analysis_post_persists_and_get_returns_result(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    _write_samples_jsonl(
        tmp_path / "run_api",
        [
            _sample_payload(0, temperature_c=0.0, distance_px=100.0),
            _sample_payload(1, temperature_c=10.0, distance_px=70.0),
            _sample_payload(2, temperature_c=20.0, distance_px=40.0),
            _sample_payload(3, temperature_c=30.0, distance_px=10.0),
            _sample_payload(4, temperature_c=40.0, distance_px=0.0),
        ],
    )
    client = TestClient(app)

    post_response = client.post("/api/runs/run_api/analysis")
    assert post_response.status_code == 200
    post_payload = post_response.json()
    assert post_payload["method"] == "af95_v1"
    assert post_payload["status"] == "ok"
    assert post_payload["result"]["af95_temperature_c"] == 35.0
    assert (tmp_path / "run_api" / "analysis.json").exists()

    get_response = client.get("/api/runs/run_api/analysis")
    assert get_response.status_code == 200
    assert get_response.json() == post_payload


def test_run_analysis_returns_explicit_status_for_missing_temperature(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    _write_samples_jsonl(
        tmp_path / "run_missing_temperature",
        [
            _sample_payload(0, temperature_c=0.0, distance_px=100.0),
            _sample_payload(1, temperature_c=None, distance_px=80.0),
            _sample_payload(2, temperature_c=20.0, distance_px=60.0),
        ],
    )
    client = TestClient(app)

    response = client.post("/api/runs/run_missing_temperature/analysis")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "insufficient_data"
    assert payload["result"] is None
    assert payload["diagnostics"]["missing_temperature_count"] == 1


def test_run_list_returns_saved_run_directories(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    run_dir = tmp_path / "run_listed"
    run_dir.mkdir()
    (run_dir / "metadata.json").write_text(
        json.dumps(
            {
                "run_id": "run_listed",
                "status": "stopped",
                "sample_hz": 10.0,
                "sample_count": 5,
                "measurement_definition_id": "md_1",
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(app)

    response = client.get("/api/runs")

    assert response.status_code == 200
    assert response.json()["runs"][0]["run_id"] == "run_listed"


def _write_samples_jsonl(run_dir: Path, rows: list[dict[str, object]]) -> None:
    run_dir.mkdir()
    payload = "\n".join(json.dumps(row) for row in rows)
    (run_dir / "samples.jsonl").write_text(payload, encoding="utf-8")


def _sample_payload(
    sample_index: int,
    *,
    temperature_c: float | None,
    distance_px: float | None,
) -> dict[str, object]:
    detection_valid = distance_px is not None
    return {
        "run_id": "run_api",
        "sample_index": sample_index,
        "timestamp_ms": sample_index * 1000,
        "temperature_c": temperature_c,
        "temperature_status": "ok" if temperature_c is not None else "unavailable",
        "detection": {
            "status": "ok" if detection_valid else "low_contrast",
            "valid": detection_valid,
            "point_a": (
                {"x": 0.0, "y": 0.0, "coordinate_space": "acquisition"} if detection_valid else None
            ),
            "point_b": (
                {"x": distance_px, "y": 0.0, "coordinate_space": "acquisition"}
                if detection_valid
                else None
            ),
            "distance_px": distance_px,
            "quality": 0.9 if detection_valid else 0.0,
            "target_family": "balloon_envelope",
            "frame_ref": None,
            "diagnostics": {
                "detector": "balloon_envelope_detector",
                "detector_version": "v1",
            },
        },
    }
