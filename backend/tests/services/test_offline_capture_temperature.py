from __future__ import annotations

from pathlib import Path

import pytest
from yyt1771_af.services.offline_capture_temperature import (
    OfflineCaptureTemperatureTrace,
    resolve_capture_temperature_csv,
)


def test_resolve_capture_temperature_csv_finds_parent_file(tmp_path: Path) -> None:
    capture_dir = tmp_path / "20260522-183158-dev_lab"
    frames_dir = capture_dir / "frames"
    frames_dir.mkdir(parents=True)
    (capture_dir / "temperature.csv").write_text(
        "frame_index,camera_timestamp_ms,temp_timestamp_ms,celsius,source,sampled_this_frame,error\n"
        "1,1000,1001,20.5,lu92xx_modbus_rtu,1,\n",
        encoding="utf-8",
    )

    resolved = resolve_capture_temperature_csv(frames_dir)
    assert resolved == capture_dir / "temperature.csv"


def test_capture_temperature_trace_lookup_by_frame_index(tmp_path: Path) -> None:
    csv_path = tmp_path / "temperature.csv"
    csv_path.write_text(
        "\n".join(
            [
                "frame_index,camera_timestamp_ms,temp_timestamp_ms,celsius,source,sampled_this_frame,error",
                "1,1000,1001,20.5,lu92xx_modbus_rtu,1,",
                "2,1100,1001,20.5,lu92xx_modbus_rtu,0,",
                "3,1200,1201,21.0,lu92xx_modbus_rtu,1,",
            ]
        ),
        encoding="utf-8",
    )
    trace = OfflineCaptureTemperatureTrace.load(csv_path)

    first = trace.runtime_payload(0)
    second = trace.runtime_payload(1)
    third = trace.runtime_payload(2)

    assert first["temperature_c"] == 20.5
    assert first["temperature_source_type"] == "capture_csv"
    assert first["temperature_source"] == "lu92xx_modbus_rtu"
    assert first["sampled_this_frame"] is True
    assert second["temperature_c"] == 20.5
    assert second["sampled_this_frame"] is False
    assert third["temperature_c"] == 21.0


def test_capture_temperature_trace_reports_row_error(tmp_path: Path) -> None:
    csv_path = tmp_path / "temperature.csv"
    csv_path.write_text(
        "frame_index,camera_timestamp_ms,temp_timestamp_ms,celsius,source,sampled_this_frame,error\n"
        "1,1000,1001,,lu92xx_modbus_rtu,1,timeout\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        OfflineCaptureTemperatureTrace.load(csv_path)
