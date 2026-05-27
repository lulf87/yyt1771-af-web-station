from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from yyt1771_af.core.models import TemperatureCommandResponse, TemperatureControllerSnapshot
from yyt1771_af.temperature.base import TemperatureController, TemperatureReading
from yyt1771_af.temperature.file import FileTemperatureController
from yyt1771_af.temperature.mock import MockTemperatureController
from yyt1771_af.temperature.serial_ascii import (
    SerialAsciiTemperatureConfig,
    SerialAsciiTemperatureController,
)
from yyt1771_af.temperature.unavailable import UnavailableTemperatureController


class TemperatureService:
    def __init__(self, controller: TemperatureController | None = None) -> None:
        self._fixed_controller = controller
        self._controller: TemperatureController | None = controller
        self._signature: tuple[str, ...] | None = None

    def read_temperature(self) -> TemperatureReading:
        return self.read_current_temperature()

    def read_current_temperature(self) -> TemperatureReading:
        return self._current_controller().read_current_temperature()

    def connect(self) -> TemperatureCommandResponse:
        return self._current_controller().connect()

    def disconnect(self) -> TemperatureCommandResponse:
        return self._current_controller().disconnect()

    def snapshot(self) -> TemperatureControllerSnapshot:
        return self._current_controller().snapshot()

    def set_target_temperature(self, target_c: float) -> TemperatureCommandResponse:
        return self._current_controller().set_target_temperature(target_c)

    def set_power_percent(self, power_percent: float) -> TemperatureCommandResponse:
        return self._current_controller().set_power_percent(power_percent)

    def set_output_enabled(self, enabled: bool) -> TemperatureCommandResponse:
        return self._current_controller().set_output_enabled(enabled)

    def metadata(self) -> dict[str, Any]:
        return self._current_controller().metadata()

    def _current_controller(self) -> TemperatureController:
        if self._fixed_controller is not None:
            return self._fixed_controller

        signature = _environment_signature()
        if self._controller is None or self._signature != signature:
            self._controller = _controller_from_signature(signature)
            self._signature = signature
        return self._controller


def _environment_signature() -> tuple[str, ...]:
    source_type = (
        os.environ.get(
            "YYT1771_AF_TEMPERATURE_CONTROLLER",
            os.environ.get("YYT1771_AF_TEMPERATURE_SOURCE", "mock"),
        )
        .strip()
        .lower()
    )
    if source_type == "file":
        return (
            source_type,
            os.environ.get("YYT1771_AF_TEMPERATURE_FILE", ""),
            os.environ.get("YYT1771_AF_TEMPERATURE_CONNECTED", "1"),
        )
    if source_type == "mock":
        return (
            source_type,
            os.environ.get("YYT1771_AF_TEMPERATURE_START_C", "0.0"),
            os.environ.get("YYT1771_AF_TEMPERATURE_END_C", "60.0"),
            os.environ.get("YYT1771_AF_TEMPERATURE_RATE_C_PER_S", "1.0"),
            os.environ.get("YYT1771_AF_TEMPERATURE_CONNECTED", "1"),
            os.environ.get("YYT1771_AF_TEMPERATURE_TARGET_C", "45.0"),
            os.environ.get("YYT1771_AF_TEMPERATURE_POWER_PERCENT", "0.0"),
        )
    if source_type == "serial_ascii":
        return (
            source_type,
            os.environ.get("YYT1771_AF_TEMPERATURE_SERIAL_PORT", ""),
            os.environ.get("YYT1771_AF_TEMPERATURE_SERIAL_BAUD_RATE", "9600"),
        )
    return (source_type,)


def _controller_from_signature(signature: tuple[str, ...]) -> TemperatureController:
    source_type = signature[0]
    try:
        if source_type == "mock":
            return MockTemperatureController(
                start_c=float(signature[1]),
                end_c=float(signature[2]),
                rate_c_per_s=float(signature[3]),
                connected=_truthy(signature[4], default=True),
                initial_target_temperature_c=float(signature[5]),
                initial_power_percent=float(signature[6]),
            )
        if source_type == "file":
            if not signature[1]:
                return UnavailableTemperatureController(
                    source_type="file",
                    message="YYT1771_AF_TEMPERATURE_FILE is required for file source.",
                )
            return FileTemperatureController(
                Path(signature[1]),
                connected=_truthy(signature[2], default=True),
            )
        if source_type == "serial_ascii":
            return SerialAsciiTemperatureController(
                SerialAsciiTemperatureConfig(
                    port=signature[1] or None,
                    baud_rate=int(signature[2]),
                    command_set={},
                )
            )
        if source_type in {"none", "disabled"}:
            return UnavailableTemperatureController(source_type="none")
        return UnavailableTemperatureController(
            source_type=source_type,
            message=f"unsupported temperature source: {source_type}",
        )
    except (FileNotFoundError, ValueError) as exc:
        return UnavailableTemperatureController(source_type=source_type, message=str(exc))


def _truthy(value: str, *, default: bool) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return default
    return normalized in {"1", "true", "yes", "on"}


temperature_service = TemperatureService()
