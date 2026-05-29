from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

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


@router.get("/debug-overlay/{debug_id}.png")
def get_setup_debug_overlay(
    debug_id: str,
    max_width: int = Query(default=1200, ge=1, le=4096),
    max_height: int | None = Query(default=None, ge=1, le=4096),
    show_raw_foreground: bool = Query(default=True),
    show_morphology_foreground: bool = Query(default=True),
    show_filled_envelope: bool = Query(default=True),
    show_selected_contour: bool = Query(default=True),
    show_rejected_candidates: bool = Query(default=True),
) -> Response:
    try:
        png = setup_service.debug_overlay_png(
            debug_id,
            max_width=max_width,
            max_height=max_height,
            show_raw_foreground=show_raw_foreground,
            show_morphology_foreground=show_morphology_foreground,
            show_filled_envelope=show_filled_envelope,
            show_selected_contour=show_selected_contour,
            show_rejected_candidates=show_rejected_candidates,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="debug overlay is not available") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(content=png, media_type="image/png")
