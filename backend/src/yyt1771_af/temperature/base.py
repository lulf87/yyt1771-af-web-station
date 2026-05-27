from __future__ import annotations

from typing import Any, Protocol

from yyt1771_af.core.models import (
    TemperatureCommandResponse,
    TemperatureControllerSnapshot,
    TemperatureReading,
)


class TemperatureSource(Protocol):
    def read_temperature(self) -> TemperatureReading:
        raise NotImplementedError

    def metadata(self) -> dict[str, Any]:
        raise NotImplementedError


class TemperatureController(Protocol):
    controller_type: str

    def connect(self) -> TemperatureCommandResponse:
        raise NotImplementedError

    def disconnect(self) -> TemperatureCommandResponse:
        raise NotImplementedError

    def snapshot(self) -> TemperatureControllerSnapshot:
        raise NotImplementedError

    def read_current_temperature(self) -> TemperatureReading:
        raise NotImplementedError

    def set_target_temperature(self, target_c: float) -> TemperatureCommandResponse:
        raise NotImplementedError

    def set_power_percent(self, power_percent: float) -> TemperatureCommandResponse:
        raise NotImplementedError

    def set_output_enabled(self, enabled: bool) -> TemperatureCommandResponse:
        raise NotImplementedError

    def metadata(self) -> dict[str, Any]:
        raise NotImplementedError
