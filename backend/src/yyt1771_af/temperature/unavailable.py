from __future__ import annotations

import time
from typing import Any

from yyt1771_af.core.models import TemperatureControllerSnapshot
from yyt1771_af.core.statuses import TemperatureStatus
from yyt1771_af.temperature.base import TemperatureCommandResponse, TemperatureReading


class UnavailableTemperatureSource:
    def __init__(self, *, source_type: str = "none", message: str | None = None) -> None:
        self.source_type = source_type
        self._message = message

    def read_temperature(self) -> TemperatureReading:
        return TemperatureReading(
            timestamp_ms=time.time_ns() // 1_000_000,
            temperature_c=None,
            status=TemperatureStatus.UNAVAILABLE,
            source_type=self.source_type,
            message=self._message,
        )

    def metadata(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_type": self.source_type,
            "status": TemperatureStatus.UNAVAILABLE.value,
        }
        if self._message is not None:
            payload["message"] = self._message
        return payload


class UnavailableTemperatureController:
    def __init__(self, *, source_type: str = "none", message: str | None = None) -> None:
        self.source_type = source_type
        self.controller_type = source_type
        self._message = message

    def connect(self) -> TemperatureCommandResponse:
        return self._response(TemperatureStatus.UNAVAILABLE)

    def disconnect(self) -> TemperatureCommandResponse:
        return self._response(TemperatureStatus.OK)

    def snapshot(self) -> TemperatureControllerSnapshot:
        return TemperatureControllerSnapshot(
            controller_type=self.controller_type,
            connected=False,
            status=TemperatureStatus.UNAVAILABLE,
            timestamp_ms=time.time_ns() // 1_000_000,
            current_temperature_c=None,
            target_temperature_c=None,
            power_percent=None,
            output_enabled=None,
            message=self._message,
        )

    def read_temperature(self) -> TemperatureReading:
        return self.read_current_temperature()

    def read_current_temperature(self) -> TemperatureReading:
        return TemperatureReading(
            timestamp_ms=time.time_ns() // 1_000_000,
            temperature_c=None,
            status=TemperatureStatus.UNAVAILABLE,
            source_type=self.source_type,
            message=self._message,
        )

    def set_target_temperature(self, target_c: float) -> TemperatureCommandResponse:
        return self._response(TemperatureStatus.UNSUPPORTED_OPERATION)

    def set_power_percent(self, power_percent: float) -> TemperatureCommandResponse:
        return self._response(TemperatureStatus.UNSUPPORTED_OPERATION)

    def set_output_enabled(self, enabled: bool) -> TemperatureCommandResponse:
        return self._response(TemperatureStatus.UNSUPPORTED_OPERATION)

    def metadata(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_type": self.source_type,
            "controller_type": self.controller_type,
            "connected": False,
            "status": TemperatureStatus.UNAVAILABLE.value,
        }
        if self._message is not None:
            payload["message"] = self._message
        return payload

    def _response(self, status: TemperatureStatus) -> TemperatureCommandResponse:
        return TemperatureCommandResponse(
            status=status,
            ok=status is TemperatureStatus.OK,
            message=self._message,
            snapshot=self.snapshot(),
        )
