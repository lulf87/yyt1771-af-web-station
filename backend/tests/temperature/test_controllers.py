from pathlib import Path

from yyt1771_af.core.statuses import TemperatureStatus
from yyt1771_af.temperature.file import FileTemperatureController
from yyt1771_af.temperature.mock import MockTemperatureController
from yyt1771_af.temperature.serial_ascii import (
    SerialAsciiTemperatureConfig,
    SerialAsciiTemperatureController,
)


class ManualClock:
    def __init__(self, seconds: float, timestamp_ms: int) -> None:
        self.seconds = seconds
        self.timestamp_ms = timestamp_ms

    def monotonic_seconds(self) -> float:
        return self.seconds

    def wall_timestamp_ms(self) -> int:
        return self.timestamp_ms


def test_mock_controller_connects_and_disconnects() -> None:
    controller = MockTemperatureController(connected=False)

    assert controller.snapshot().connected is False
    assert controller.snapshot().status is TemperatureStatus.DISCONNECTED

    connected = controller.connect()
    assert connected.status is TemperatureStatus.OK
    assert connected.snapshot.connected is True

    disconnected = controller.disconnect()
    assert disconnected.status is TemperatureStatus.OK
    assert disconnected.snapshot.connected is False
    assert disconnected.snapshot.status is TemperatureStatus.DISCONNECTED


def test_mock_controller_reads_current_temperature() -> None:
    clock = ManualClock(seconds=10.0, timestamp_ms=10_000)
    controller = MockTemperatureController(
        start_c=20.0,
        end_c=60.0,
        rate_c_per_s=2.0,
        connected=True,
        monotonic_seconds=clock.monotonic_seconds,
        timestamp_ms=clock.wall_timestamp_ms,
    )

    first = controller.read_current_temperature()
    clock.seconds = 15.0
    clock.timestamp_ms = 15_000
    second = controller.read_current_temperature()

    assert first.status is TemperatureStatus.OK
    assert first.temperature_c == 20.0
    assert first.source_type == "mock"
    assert second.status is TemperatureStatus.OK
    assert second.temperature_c == 30.0


def test_mock_controller_sets_target_and_power() -> None:
    controller = MockTemperatureController(connected=True)

    target_response = controller.set_target_temperature(45.5)
    power_response = controller.set_power_percent(40.0)
    output_response = controller.set_output_enabled(True)

    assert target_response.status is TemperatureStatus.OK
    assert target_response.snapshot.target_temperature_c == 45.5
    assert power_response.status is TemperatureStatus.OK
    assert power_response.snapshot.power_percent == 40.0
    assert output_response.status is TemperatureStatus.OK
    assert output_response.snapshot.output_enabled is True


def test_mock_controller_rejects_invalid_power_percent() -> None:
    controller = MockTemperatureController(connected=True, initial_power_percent=10.0)

    response = controller.set_power_percent(125.0)

    assert response.status is TemperatureStatus.INVALID_REQUEST
    assert response.snapshot.power_percent == 10.0


def test_file_temperature_controller_replays_file_and_rejects_set_operations(
    tmp_path: Path,
) -> None:
    path = tmp_path / "temperature.csv"
    path.write_text("timestamp_ms,temperature_c\n1000,22.5\n", encoding="utf-8")
    controller = FileTemperatureController(path, connected=True)

    reading = controller.read_current_temperature()
    target_response = controller.set_target_temperature(42.0)
    power_response = controller.set_power_percent(20.0)

    assert reading.status is TemperatureStatus.OK
    assert reading.temperature_c == 22.5
    assert reading.source_type == "file"
    assert target_response.status is TemperatureStatus.UNSUPPORTED_OPERATION
    assert power_response.status is TemperatureStatus.UNSUPPORTED_OPERATION


def test_serial_ascii_controller_construction_does_not_open_port() -> None:
    controller = SerialAsciiTemperatureController(
        SerialAsciiTemperatureConfig(
            port="configured-by-local-profile",
            command_set={},
        )
    )

    snapshot = controller.snapshot()

    assert snapshot.controller_type == "serial_ascii"
    assert snapshot.connected is False
    assert snapshot.status is TemperatureStatus.DISCONNECTED


def test_serial_ascii_missing_command_set_returns_unsupported_protocol() -> None:
    controller = SerialAsciiTemperatureController(
        SerialAsciiTemperatureConfig(
            port="configured-by-local-profile",
            command_set={},
        )
    )

    reading = controller.read_current_temperature()
    response = controller.set_target_temperature(40.0)

    assert reading.status is TemperatureStatus.UNSUPPORTED_PROTOCOL
    assert reading.temperature_c is None
    assert response.status is TemperatureStatus.UNSUPPORTED_PROTOCOL
