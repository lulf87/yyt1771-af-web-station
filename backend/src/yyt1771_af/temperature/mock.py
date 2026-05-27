from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from yyt1771_af.core.models import TemperatureControllerSnapshot
from yyt1771_af.core.statuses import TemperatureStatus
from yyt1771_af.temperature.base import TemperatureCommandResponse, TemperatureReading


class MockTemperatureSource:
    source_type = "mock"

    def __init__(
        self,
        *,
        start_c: float = 0.0,
        end_c: float = 60.0,
        rate_c_per_s: float = 1.0,
        monotonic_seconds: Callable[[], float] = time.monotonic,
        timestamp_ms: Callable[[], int] | None = None,
    ) -> None:
        if end_c < start_c:
            raise ValueError("mock temperature end_c must be greater than or equal to start_c")
        if rate_c_per_s <= 0.0:
            raise ValueError("mock temperature rate_c_per_s must be positive")
        self._start_c = start_c
        self._end_c = end_c
        self._rate_c_per_s = rate_c_per_s
        self._monotonic_seconds = monotonic_seconds
        self._timestamp_ms = timestamp_ms or _timestamp_ms
        self._start_seconds: float | None = None

    def read_temperature(self) -> TemperatureReading:
        now_seconds = self._monotonic_seconds()
        if self._start_seconds is None:
            self._start_seconds = now_seconds

        elapsed_seconds = max(0.0, now_seconds - self._start_seconds)
        temperature_c = min(self._end_c, self._start_c + elapsed_seconds * self._rate_c_per_s)
        return TemperatureReading(
            timestamp_ms=self._timestamp_ms(),
            temperature_c=round(temperature_c, 6),
            status=TemperatureStatus.OK,
            source_type=self.source_type,
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "start_c": self._start_c,
            "end_c": self._end_c,
            "rate_c_per_s": self._rate_c_per_s,
        }


def _timestamp_ms() -> int:
    return time.time_ns() // 1_000_000


class MockTemperatureController:
    controller_type = "mock"
    source_type = "mock"

    def __init__(
        self,
        *,
        start_c: float = 0.0,
        end_c: float = 60.0,
        rate_c_per_s: float = 1.0,
        connected: bool = False,
        initial_target_temperature_c: float | None = 45.0,
        initial_power_percent: float = 0.0,
        output_enabled: bool = False,
        monotonic_seconds: Callable[[], float] = time.monotonic,
        timestamp_ms: Callable[[], int] | None = None,
    ) -> None:
        if initial_power_percent < 0.0 or initial_power_percent > 100.0:
            raise ValueError("mock temperature initial_power_percent must be 0..100")
        self._source = MockTemperatureSource(
            start_c=start_c,
            end_c=end_c,
            rate_c_per_s=rate_c_per_s,
            monotonic_seconds=monotonic_seconds,
            timestamp_ms=timestamp_ms,
        )
        self._connected = connected
        self._target_temperature_c = initial_target_temperature_c
        self._power_percent = initial_power_percent
        self._output_enabled = output_enabled
        self._timestamp_ms = timestamp_ms or _timestamp_ms
        self._last_temperature_c: float | None = start_c if connected else None

    def connect(self) -> TemperatureCommandResponse:
        self._connected = True
        return self._response(TemperatureStatus.OK, message="mock temperature controller connected")

    def disconnect(self) -> TemperatureCommandResponse:
        self._connected = False
        return self._response(
            TemperatureStatus.OK,
            message="mock temperature controller disconnected",
        )

    def snapshot(self) -> TemperatureControllerSnapshot:
        status = TemperatureStatus.OK if self._connected else TemperatureStatus.DISCONNECTED
        return TemperatureControllerSnapshot(
            controller_type=self.controller_type,
            connected=self._connected,
            status=status,
            timestamp_ms=self._timestamp_ms(),
            current_temperature_c=self._last_temperature_c if self._connected else None,
            target_temperature_c=self._target_temperature_c,
            power_percent=self._power_percent,
            output_enabled=self._output_enabled,
        )

    def read_temperature(self) -> TemperatureReading:
        return self.read_current_temperature()

    def read_current_temperature(self) -> TemperatureReading:
        if not self._connected:
            return TemperatureReading(
                timestamp_ms=self._timestamp_ms(),
                temperature_c=None,
                status=TemperatureStatus.NOT_CONNECTED,
                source_type=self.source_type,
                message="temperature controller is not connected",
            )

        reading = self._source.read_temperature()
        self._last_temperature_c = reading.temperature_c
        return reading

    def set_target_temperature(self, target_c: float) -> TemperatureCommandResponse:
        if target_c < -273.15 or target_c > 300.0:
            return self._response(
                TemperatureStatus.INVALID_REQUEST,
                message="target_c must be between -273.15 and 300.0",
            )
        self._target_temperature_c = target_c
        return self._response(TemperatureStatus.OK)

    def set_power_percent(self, power_percent: float) -> TemperatureCommandResponse:
        if power_percent < 0.0 or power_percent > 100.0:
            return self._response(
                TemperatureStatus.INVALID_REQUEST,
                message="power_percent must be between 0 and 100",
            )
        self._power_percent = power_percent
        return self._response(TemperatureStatus.OK)

    def set_output_enabled(self, enabled: bool) -> TemperatureCommandResponse:
        self._output_enabled = enabled
        return self._response(TemperatureStatus.OK)

    def metadata(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "controller_type": self.controller_type,
            "connected": self._connected,
            "status": self.snapshot().status.value,
        } | self._source.metadata()

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
