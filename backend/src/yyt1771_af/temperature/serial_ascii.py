from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from yyt1771_af.core.models import TemperatureControllerSnapshot
from yyt1771_af.core.statuses import TemperatureStatus
from yyt1771_af.temperature.base import TemperatureCommandResponse, TemperatureReading


@dataclass(frozen=True, slots=True)
class SerialAsciiTemperatureConfig:
    port: str | None = None
    baud_rate: int = 9600
    bytesize: int = 8
    parity: str = "N"
    stopbits: int = 1
    timeout_s: float = 1.0
    write_timeout_s: float = 1.0
    command_set: dict[str, str | None] = field(default_factory=dict)


class SerialAsciiTemperatureController:
    controller_type = "serial_ascii"
    source_type = "serial_ascii"

    def __init__(self, config: SerialAsciiTemperatureConfig) -> None:
        self._config = config
        self._connected = False
        self._serial_handle: Any | None = None
        self._message: str | None = None

    def connect(self) -> TemperatureCommandResponse:
        if self._missing_command("read_current_temperature"):
            return self._response(
                TemperatureStatus.UNSUPPORTED_PROTOCOL,
                message="serial_ascii command_set.read_current_temperature is required",
            )
        if not self._config.port:
            return self._response(
                TemperatureStatus.INVALID_REQUEST,
                message="serial_ascii port must be configured outside committed defaults",
            )

        try:
            serial_module = __import__("serial")
        except ImportError:
            return self._response(
                TemperatureStatus.COMMUNICATION_ERROR,
                message="pyserial is not installed; mock/offline modes do not require it",
            )

        try:
            self._serial_handle = serial_module.Serial(
                port=self._config.port,
                baudrate=self._config.baud_rate,
                bytesize=self._config.bytesize,
                parity=self._config.parity,
                stopbits=self._config.stopbits,
                timeout=self._config.timeout_s,
                write_timeout=self._config.write_timeout_s,
            )
        except Exception as exc:  # pragma: no cover - depends on lab hardware/driver.
            return self._response(TemperatureStatus.COMMUNICATION_ERROR, message=str(exc))

        self._connected = True
        return self._response(TemperatureStatus.OK)

    def disconnect(self) -> TemperatureCommandResponse:
        handle = self._serial_handle
        self._serial_handle = None
        self._connected = False
        if handle is not None:
            try:
                handle.close()
            except Exception as exc:  # pragma: no cover - depends on serial backend.
                return self._response(TemperatureStatus.COMMUNICATION_ERROR, message=str(exc))
        return self._response(TemperatureStatus.OK)

    def snapshot(self) -> TemperatureControllerSnapshot:
        return TemperatureControllerSnapshot(
            controller_type=self.controller_type,
            connected=self._connected,
            status=TemperatureStatus.OK if self._connected else TemperatureStatus.DISCONNECTED,
            timestamp_ms=_timestamp_ms(),
            current_temperature_c=None,
            target_temperature_c=None,
            power_percent=None,
            output_enabled=None,
            message=self._message,
        )

    def read_temperature(self) -> TemperatureReading:
        return self.read_current_temperature()

    def read_current_temperature(self) -> TemperatureReading:
        if self._missing_command("read_current_temperature"):
            return self._reading(
                TemperatureStatus.UNSUPPORTED_PROTOCOL,
                message="serial_ascii command_set.read_current_temperature is required",
            )
        if not self._connected:
            return self._reading(
                TemperatureStatus.NOT_CONNECTED,
                message="serial_ascii temperature controller is not connected",
            )
        return self._reading(
            TemperatureStatus.UNSUPPORTED_PROTOCOL,
            message="serial_ascii response parsing requires a configured lab protocol",
        )

    def set_target_temperature(self, target_c: float) -> TemperatureCommandResponse:
        return self._unsupported_if_missing("set_target_temperature")

    def set_power_percent(self, power_percent: float) -> TemperatureCommandResponse:
        if power_percent < 0.0 or power_percent > 100.0:
            return self._response(
                TemperatureStatus.INVALID_REQUEST,
                message="power_percent must be between 0 and 100",
            )
        return self._unsupported_if_missing("set_power_percent")

    def set_output_enabled(self, enabled: bool) -> TemperatureCommandResponse:
        return self._unsupported_if_missing("set_output_enabled")

    def metadata(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "controller_type": self.controller_type,
            "connected": self._connected,
            "status": self.snapshot().status.value,
            "protocol_configured": bool(self._config.command_set),
        }

    def _unsupported_if_missing(self, command_name: str) -> TemperatureCommandResponse:
        if self._missing_command(command_name):
            return self._response(
                TemperatureStatus.UNSUPPORTED_PROTOCOL,
                message=f"serial_ascii command_set.{command_name} is required",
            )
        if not self._connected:
            return self._response(
                TemperatureStatus.NOT_CONNECTED,
                message="serial_ascii temperature controller is not connected",
            )
        return self._response(
            TemperatureStatus.UNSUPPORTED_PROTOCOL,
            message="serial_ascii command execution requires a configured lab protocol",
        )

    def _missing_command(self, command_name: str) -> bool:
        return not self._config.command_set.get(command_name)

    def _reading(self, status: TemperatureStatus, *, message: str) -> TemperatureReading:
        self._message = message
        return TemperatureReading(
            timestamp_ms=_timestamp_ms(),
            temperature_c=None,
            status=status,
            source_type=self.source_type,
            message=message,
        )

    def _response(
        self,
        status: TemperatureStatus,
        *,
        message: str | None = None,
    ) -> TemperatureCommandResponse:
        self._message = message
        return TemperatureCommandResponse(
            status=status,
            ok=status is TemperatureStatus.OK,
            message=message,
            snapshot=self.snapshot(),
        )


def _timestamp_ms() -> int:
    return time.time_ns() // 1_000_000
