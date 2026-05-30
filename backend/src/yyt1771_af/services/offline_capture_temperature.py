from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CaptureTemperatureRow:
    frame_index: int
    camera_timestamp_ms: int
    temp_timestamp_ms: int
    celsius: float
    source: str
    sampled_this_frame: bool
    error: str | None


class OfflineCaptureTemperatureTrace:
    """Frame-indexed temperature trace from a camera capture ``temperature.csv``."""

    def __init__(self, rows_by_frame_index: dict[int, CaptureTemperatureRow]) -> None:
        self._rows_by_frame_index = rows_by_frame_index

    @classmethod
    def load(cls, path: Path) -> OfflineCaptureTemperatureTrace:
        rows: dict[int, CaptureTemperatureRow] = {}
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                if raw is None:
                    continue
                row = _parse_capture_temperature_row(raw)
                rows[row.frame_index] = row
        if not rows:
            raise ValueError("capture temperature.csv does not contain any rows")
        return cls(rows)

    @property
    def row_count(self) -> int:
        return len(self._rows_by_frame_index)

    def runtime_payload(self, frame_index: int) -> dict[str, Any]:
        """Lookup by offline-run frame index (0-based). CSV uses 1-based frame_index."""
        row = self._rows_by_frame_index.get(frame_index + 1)
        if row is None:
            return {
                "temperature_c": None,
                "temperature_status": "unavailable",
                "temperature_source_type": "capture_csv",
                "temperature_message": "no temperature row for frame",
            }
        if row.error:
            return {
                "temperature_c": None,
                "temperature_status": "error",
                "temperature_source_type": "capture_csv",
                "temperature_source": row.source,
                "temperature_message": row.error,
                "temp_timestamp_ms": row.temp_timestamp_ms,
                "sampled_this_frame": row.sampled_this_frame,
            }
        return {
            "temperature_c": round(row.celsius, 2),
            "temperature_status": "ok",
            "temperature_source_type": "capture_csv",
            "temperature_source": row.source,
            "temp_timestamp_ms": row.temp_timestamp_ms,
            "sampled_this_frame": row.sampled_this_frame,
        }


def resolve_capture_temperature_csv(frames_dir: Path) -> Path | None:
    """Find ``temperature.csv`` for a capture whose frames live under ``frames/``."""
    candidates = (
        frames_dir.parent / "temperature.csv",
        frames_dir / "temperature.csv",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _parse_capture_temperature_row(raw: dict[str, str | None]) -> CaptureTemperatureRow:
    frame_index_raw = raw.get("frame_index")
    celsius_raw = raw.get("celsius")
    if frame_index_raw is None or frame_index_raw.strip() == "":
        raise ValueError("capture temperature row requires frame_index")
    if celsius_raw is None or celsius_raw.strip() == "":
        raise ValueError("capture temperature row requires celsius")
    error_value = raw.get("error")
    error = error_value.strip() if isinstance(error_value, str) and error_value.strip() else None
    sampled_raw = raw.get("sampled_this_frame", "0")
    sampled = str(sampled_raw).strip() in {"1", "true", "True", "yes"}
    source = str(raw.get("source") or "capture_csv")
    return CaptureTemperatureRow(
        frame_index=int(frame_index_raw),
        camera_timestamp_ms=int(raw.get("camera_timestamp_ms") or 0),
        temp_timestamp_ms=int(raw.get("temp_timestamp_ms") or 0),
        celsius=float(celsius_raw),
        source=source,
        sampled_this_frame=sampled,
        error=error,
    )
