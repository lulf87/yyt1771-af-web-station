import csv
import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from yyt1771_af.main import app


def test_csv_export_contains_required_sample_columns(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    _write_run_artifacts(tmp_path / "run_export")
    client = TestClient(app)

    response = client.get("/api/runs/run_export/export.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert _content_disposition_filename(response) == "run_export_export.csv"
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows[0] == {
        "frame_id": "11",
        "timestamp": "1000",
        "temperature_c": "10.0",
        "detection_status": "ok",
        "point_a_x": "1.0",
        "point_a_y": "2.0",
        "point_b_x": "6.0",
        "point_b_y": "2.0",
        "distance_px": "5.0",
        "quality": "0.91",
        "reason": "",
    }
    assert rows[1]["detection_status"] == "low_contrast"
    assert rows[1]["distance_px"] == ""
    assert rows[1]["reason"] == "low contrast"


def test_json_export_contains_metadata_definition_samples_and_analysis(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    _write_run_artifacts(tmp_path / "run_export")
    client = TestClient(app)

    response = client.get("/api/runs/run_export/export.json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert payload["run_metadata"]["run_id"] == "run_export"
    assert payload["measurement_definition"]["detector_version"] == "v1"
    assert payload["detector_version"] == "v1"
    assert payload["recipe"]["name"] == "balloon_envelope_default"
    assert len(payload["samples"]) == 2
    assert payload["analysis_result"]["result"]["af95_temperature_c"] == 30.0


def test_json_export_redacts_absolute_paths_from_run_metadata(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    _write_run_artifacts(
        tmp_path / "run_export",
        metadata_extra={
            "temperature_source": {
                "source_type": "file",
                "path": "/Users/lab/private/temps.csv",
                "windows_path": r"C:\Users\lab\private\temps_windows.csv",
            },
            "nested": {
                "config_path": "/Users/lab/private/configs/temperature.local.yaml",
            },
        },
    )
    client = TestClient(app)

    response = client.get("/api/runs/run_export/export.json")

    assert response.status_code == 200
    text = response.text
    payload = response.json()
    assert "/Users" not in text
    assert "C:\\Users" not in text
    assert "C:\\\\Users" not in text
    assert "private" not in text
    assert payload["run_metadata"]["temperature_source"]["path"] == "temps.csv"
    assert payload["run_metadata"]["temperature_source"]["windows_path"] == "temps_windows.csv"
    assert payload["run_metadata"]["nested"]["config_path"] == "temperature.local.yaml"


def test_xlsx_export_redacts_absolute_paths_from_metadata_sheet(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    _write_run_artifacts(
        tmp_path / "run_export",
        metadata_extra={
            "temperature_source": {
                "source_type": "file",
                "path": "/Users/lab/private/temps.csv",
                "windows_path": r"C:\Users\lab\private\temps_windows.csv",
            },
        },
    )
    client = TestClient(app)

    response = client.get("/api/runs/run_export/export.xlsx")

    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as workbook:
        worksheet_xml = "\n".join(
            workbook.read(name).decode("utf-8")
            for name in workbook.namelist()
            if name.startswith("xl/worksheets/")
        )
    assert "/Users" not in worksheet_xml
    assert "C:\\Users" not in worksheet_xml
    assert "C:\\\\Users" not in worksheet_xml
    assert "private" not in worksheet_xml
    assert "temps.csv" in worksheet_xml
    assert "temps_windows.csv" in worksheet_xml


def test_png_export_returns_png_curve_bytes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    _write_run_artifacts(tmp_path / "run_export")
    client = TestClient(app)

    response = client.get("/api/runs/run_export/export.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"IEND" in response.content[-32:]


def test_xlsx_export_contains_expected_sheets(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    _write_run_artifacts(tmp_path / "run_export")
    client = TestClient(app)

    response = client.get("/api/runs/run_export/export.xlsx")

    assert response.status_code == 200
    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    with zipfile.ZipFile(io.BytesIO(response.content)) as workbook:
        names = set(workbook.namelist())
        assert "xl/workbook.xml" in names
        assert "xl/worksheets/sheet1.xml" in names
        workbook_xml = workbook.read("xl/workbook.xml").decode("utf-8")
        assert "Summary" in workbook_xml
        assert "Samples" in workbook_xml
        assert "Analysis" in workbook_xml
        assert "Metadata" in workbook_xml


def test_export_filename_sanitizes_windows_invalid_run_id(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("YYT1771_AF_RUNS_DIR", str(tmp_path))
    _write_run_artifacts(tmp_path / "run bad name")
    client = TestClient(app)

    response = client.get("/api/runs/run%20bad%20name/export.csv")

    assert response.status_code == 200
    assert _content_disposition_filename(response) == "run_bad_name_export.csv"


def _content_disposition_filename(response) -> str:
    value = response.headers["content-disposition"]
    marker = "filename="
    return value[value.index(marker) + len(marker) :].strip('"')


def _write_run_artifacts(
    run_dir: Path,
    *,
    metadata_extra: dict[str, object] | None = None,
) -> None:
    run_dir.mkdir()
    metadata = {
        "run_id": run_dir.name,
        "status": "stopped",
        "sample_hz": 10.0,
        "sample_count": 2,
        "measurement_definition_id": "md_export",
    }
    if metadata_extra is not None:
        metadata.update(metadata_extra)
    (run_dir / "metadata.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )
    (run_dir / "measurement_definition.json").write_text(
        json.dumps(
            {
                "measurement_definition_id": "md_export",
                "name": "export-definition",
                "target_family": "balloon_envelope",
                "roi": {
                    "center_x": 110.0,
                    "center_y": 110.0,
                    "width": 130.0,
                    "height": 80.0,
                    "angle_deg": 0.0,
                    "coordinate_space": "acquisition",
                },
                "recipe_name": "balloon_envelope_default",
                "detector_version": "v1",
                "acquisition_frame_size": {"width": 320, "height": 220},
                "coordinate_space": "acquisition",
                "created_at_ms": 1000,
            }
        ),
        encoding="utf-8",
    )
    samples = [
        _sample_payload(0, frame_id=11, temperature_c=10.0, distance_px=5.0),
        _sample_payload(
            1,
            frame_id=12,
            temperature_c=11.0,
            distance_px=None,
            status="low_contrast",
            reason="low contrast",
        ),
    ]
    (run_dir / "samples.jsonl").write_text(
        "\n".join(json.dumps(sample) for sample in samples),
        encoding="utf-8",
    )
    (run_dir / "analysis.json").write_text(
        json.dumps(
            {
                "method": "af95_v1",
                "status": "ok",
                "curve": [
                    {
                        "sample_index": 0,
                        "timestamp_ms": 1000,
                        "temperature_c": 10.0,
                        "distance_px": 5.0,
                        "recovered_fraction": 0.0,
                    },
                    {
                        "sample_index": 2,
                        "timestamp_ms": 3000,
                        "temperature_c": 40.0,
                        "distance_px": 0.0,
                        "recovered_fraction": 1.0,
                    },
                ],
                "result": {
                    "min_distance_px": 0.0,
                    "max_distance_px": 5.0,
                    "initial_distance_px": 5.0,
                    "final_distance_px": 0.0,
                    "recovered_fraction": 1.0,
                    "valid_sample_count": 2,
                    "invalid_sample_count": 1,
                    "temperature_range": [10.0, 40.0],
                    "af95_temperature_c": 30.0,
                },
                "diagnostics": {"invalid_sample_count": 1},
            }
        ),
        encoding="utf-8",
    )


def _sample_payload(
    sample_index: int,
    *,
    frame_id: int,
    temperature_c: float,
    distance_px: float | None,
    status: str = "ok",
    reason: str | None = None,
) -> dict[str, object]:
    valid = distance_px is not None
    return {
        "run_id": "run_export",
        "sample_index": sample_index,
        "timestamp_ms": 1000 + sample_index * 1000,
        "temperature_c": temperature_c,
        "temperature_status": "ok",
        "detection": {
            "status": status,
            "valid": valid,
            "point_a": {"x": 1.0, "y": 2.0, "coordinate_space": "acquisition"} if valid else None,
            "point_b": ({"x": 6.0, "y": 2.0, "coordinate_space": "acquisition"} if valid else None),
            "distance_px": distance_px,
            "quality": 0.91 if valid else 0.0,
            "target_family": "balloon_envelope",
            "frame_ref": {
                "frame_id": frame_id,
                "timestamp_ms": 1000 + sample_index * 1000,
                "width": 320,
                "height": 220,
                "coordinate_space": "acquisition",
            },
            "diagnostics": {
                "detector": "balloon_envelope_detector",
                "detector_version": "v1",
                "message": reason,
            },
        },
    }
