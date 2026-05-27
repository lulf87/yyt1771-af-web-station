from __future__ import annotations

from fastapi import APIRouter, HTTPException

from yyt1771_af.services.setup_service import (
    FreezeRequest,
    FreezeResponse,
    SetupConfirmRequest,
    SetupConfirmResponse,
    SetupDetectRequest,
    SetupDetectResponse,
    setup_service,
)

router = APIRouter(prefix="/setup", tags=["setup"])


@router.post("/freeze", response_model=FreezeResponse)
def freeze_setup_frame(request: FreezeRequest) -> FreezeResponse:
    try:
        return setup_service.freeze(request)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/detect", response_model=SetupDetectResponse)
def detect_setup_frame(request: SetupDetectRequest) -> SetupDetectResponse:
    try:
        return setup_service.detect(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/confirm", response_model=SetupConfirmResponse)
def confirm_setup(request: SetupConfirmRequest) -> SetupConfirmResponse:
    try:
        return setup_service.confirm(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
