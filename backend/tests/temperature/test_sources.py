import json
from pathlib import Path

from yyt1771_af.core.statuses import TemperatureStatus
from yyt1771_af.temperature.file import FileTemperatureSource
from yyt1771_af.temperature.mock import MockTemperatureSource


class ManualClock:
    def __init__(self, seconds: float, timestamp_ms: int) -> None:
        self.seconds = seconds
        self.timestamp_ms = timestamp_ms

    def monotonic_seconds(self) -> float:
        return self.seconds

    def wall_timestamp_ms(self) -> int:
        return self.timestamp_ms


def test_mock_temperature_source_generates_linear_ramp() -> None:
    clock = ManualClock(seconds=10.0, timestamp_ms=10_000)
    source = MockTemperatureSource(
        start_c=0.0,
        end_c=60.0,
        rate_c_per_s=2.5,
        monotonic_seconds=clock.monotonic_seconds,
        timestamp_ms=clock.wall_timestamp_ms,
    )

    first = source.read_temperature()
    clock.seconds = 18.0
    clock.timestamp_ms = 18_000
    second = source.read_temperature()
    clock.seconds = 100.0
    clock.timestamp_ms = 100_000
    capped = source.read_temperature()

    assert first.timestamp_ms == 10_000
    assert first.temperature_c == 0.0
    assert first.status is TemperatureStatus.OK
    assert second.timestamp_ms == 18_000
    assert second.temperature_c == 20.0
    assert second.status is TemperatureStatus.OK
    assert capped.temperature_c == 60.0


def test_file_temperature_source_reads_csv_rows(tmp_path: Path) -> None:
    path = tmp_path / "temperatures.csv"
    path.write_text(
        "timestamp_ms,temperature_c\n1000,12.5\n2000,13.75\n",
        encoding="utf-8",
    )
    source = FileTemperatureSource(path)

    first = source.read_temperature()
    second = source.read_temperature()
    exhausted = source.read_temperature()

    assert first.timestamp_ms == 1000
    assert first.temperature_c == 12.5
    assert first.status is TemperatureStatus.OK
    assert second.timestamp_ms == 2000
    assert second.temperature_c == 13.75
    assert second.status is TemperatureStatus.OK
    assert exhausted.temperature_c is None
    assert exhausted.status is TemperatureStatus.UNAVAILABLE


def test_file_temperature_source_reads_jsonl_rows(tmp_path: Path) -> None:
    path = tmp_path / "temperatures.jsonl"
    rows = [
        {"timestamp_ms": 3000, "temperature_c": 22.0},
        {"timestamp_ms": 4000, "temperature_c": 23.5},
    ]
    path.write_text(
        "\n".join(json.dumps(row) for row in rows),
        encoding="utf-8",
    )
    source = FileTemperatureSource(path)

    assert source.read_temperature().temperature_c == 22.0
    assert source.read_temperature().temperature_c == 23.5
