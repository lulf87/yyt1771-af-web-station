from __future__ import annotations

from fastapi import APIRouter

from yyt1771_af.core.models import (
    TemperatureCommandResponse,
    TemperatureControllerSnapshot,
    TemperatureOutputRequest,
    TemperaturePowerRequest,
    TemperatureReading,
    TemperatureTargetRequest,
)
from yyt1771_af.services.temperature_service import temperature_service

router = APIRouter(prefix="/temperature", tags=["temperature"])


@router.get("/status", response_model=TemperatureControllerSnapshot)
def get_temperature_status() -> TemperatureControllerSnapshot:
    return temperature_service.snapshot()


@router.post("/connect", response_model=TemperatureCommandResponse)
def connect_temperature_controller() -> TemperatureCommandResponse:
    return temperature_service.connect()


@router.post("/disconnect", response_model=TemperatureCommandResponse)
def disconnect_temperature_controller() -> TemperatureCommandResponse:
    return temperature_service.disconnect()


@router.get("/current", response_model=TemperatureReading)
def get_current_temperature() -> TemperatureReading:
    return temperature_service.read_current_temperature()


@router.post("/target", response_model=TemperatureCommandResponse)
def set_temperature_target(request: TemperatureTargetRequest) -> TemperatureCommandResponse:
    return temperature_service.set_target_temperature(request.target_c)


@router.post("/power", response_model=TemperatureCommandResponse)
def set_temperature_power(request: TemperaturePowerRequest) -> TemperatureCommandResponse:
    return temperature_service.set_power_percent(request.power_percent)


@router.post("/output", response_model=TemperatureCommandResponse)
def set_temperature_output(request: TemperatureOutputRequest) -> TemperatureCommandResponse:
    return temperature_service.set_output_enabled(request.enabled)
