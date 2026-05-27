from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any

from yyt1771_af.core.models import TemperatureControllerSnapshot
from yyt1771_af.core.statuses import TemperatureStatus
from yyt1771_af.temperature.base import TemperatureCommandResponse, TemperatureReading


class FileTemperatureSource:
    source_type = "file"

    def __init__(self, path: Path) -> None:
        self._path = path
        self._rows = _load_rows(path)
        self._index = 0

    def read_temperature(self) -> TemperatureReading:
        if self._index >= len(self._rows):
            return TemperatureReading(
                timestamp_ms=_timestamp_ms(),
                temperature_c=None,
                status=TemperatureStatus.UNAVAILABLE,
                source_type=self.source_type,
                message="temperature file replay is exhausted",
            )

        row = self._rows[self._index]
        self._index += 1
        return TemperatureReading(
            timestamp_ms=row["timestamp_ms"],
            temperature_c=row["temperature_c"],
            status=TemperatureStatus.OK,
            source_type=self.source_type,
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "filename": self._path.name,
            "row_count": len(self._rows),
        }


class FileTemperatureController:
    controller_type = "file"
    source_type = "file"

    def __init__(self, path: Path, *, connected: bool = False) -> None:
        self._source = FileTemperatureSource(path)
        self._connected = connected
        self._last_temperature_c: float | None = None

    def connect(self) -> TemperatureCommandResponse:
        self._connected = True
        return self._response(TemperatureStatus.OK, message="file temperature replay connected")

    def disconnect(self) -> TemperatureCommandResponse:
        self._connected = False
        return self._response(TemperatureStatus.OK, message="file temperature replay disconnected")

    def snapshot(self) -> TemperatureControllerSnapshot:
        return TemperatureControllerSnapshot(
            controller_type=self.controller_type,
            connected=self._connected,
            status=TemperatureStatus.OK if self._connected else TemperatureStatus.DISCONNECTED,
            timestamp_ms=_timestamp_ms(),
            current_temperature_c=self._last_temperature_c if self._connected else None,
            target_temperature_c=None,
            power_percent=None,
            output_enabled=None,
        )

    def read_temperature(self) -> TemperatureReading:
        return self.read_current_temperature()

    def read_current_temperature(self) -> TemperatureReading:
        if not self._connected:
            return TemperatureReading(
                timestamp_ms=_timestamp_ms(),
                temperature_c=None,
                status=TemperatureStatus.NOT_CONNECTED,
                source_type=self.source_type,
                message="temperature file replay is not connected",
            )
        reading = self._source.read_temperature()
        self._last_temperature_c = reading.temperature_c
        return reading

    def set_target_temperature(self, target_c: float) -> TemperatureCommandResponse:
        return self._unsupported("file temperature replay cannot set target temperature")

    def set_power_percent(self, power_percent: float) -> TemperatureCommandResponse:
        return self._unsupported("file temperature replay cannot set power percent")

    def set_output_enabled(self, enabled: bool) -> TemperatureCommandResponse:
        return self._unsupported("file temperature replay cannot set output state")

    def metadata(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "controller_type": self.controller_type,
            "connected": self._connected,
            "status": self.snapshot().status.value,
        } | self._source.metadata()

    def _unsupported(self, message: str) -> TemperatureCommandResponse:
        return self._response(TemperatureStatus.UNSUPPORTED_OPERATION, message=message)

    def _response(
        self,
        status: TemperatureStatus,
        *,
        message: str | None = None,
    ) -> TemperatureCommandResponse:
        return TemperatureCommandResponse(
            status=status,
            ok=status is TemperatureStatus.OK,
            message=message,
            snapshot=self.snapshot(),
        )


def _load_rows(path: Path) -> list[dict[str, int | float]]:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"temperature file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _load_csv_rows(path)
    if suffix == ".jsonl":
        return _load_jsonl_rows(path)
    raise ValueError("temperature file must be .csv or .jsonl")


def _load_csv_rows(path: Path) -> list[dict[str, int | float]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [_parse_row(row) for row in reader]


def _load_jsonl_rows(path: Path) -> list[dict[str, int | float]]:
    rows: list[dict[str, int | float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(_parse_row(json.loads(line)))
    return rows


def _parse_row(row: dict[str, Any]) -> dict[str, int | float]:
    timestamp_value = row.get("timestamp_ms", row.get("timestamp"))
    temperature_value = row.get("temperature_c")
    if timestamp_value is None or temperature_value is None:
        raise ValueError("temperature rows require timestamp_ms and temperature_c")
    return {
        "timestamp_ms": int(timestamp_value),
        "temperature_c": float(temperature_value),
    }


def _timestamp_ms() -> int:
    return time.time_ns() // 1_000_000
