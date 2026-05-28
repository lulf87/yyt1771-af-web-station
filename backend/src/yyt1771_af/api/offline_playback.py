from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from yyt1771_af.services.offline_playback_service import (
    OfflinePlaybackFrameResponse,
    OfflinePlaybackOpenRequest,
    OfflinePlaybackSeekRequest,
    OfflinePlaybackStatusResponse,
    OfflinePlaybackStepRequest,
    offline_playback_service,
)

router = APIRouter(prefix="/offline-playback", tags=["offline-playback"])


@router.post("/open", response_model=OfflinePlaybackStatusResponse)
def open_offline_playback(
    request: OfflinePlaybackOpenRequest,
) -> OfflinePlaybackStatusResponse:
    try:
        return offline_playback_service.open(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=_safe_error_detail(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=_safe_error_detail(exc)) from exc


@router.get("/status", response_model=OfflinePlaybackStatusResponse)
def get_offline_playback_status() -> OfflinePlaybackStatusResponse:
    try:
        return offline_playback_service.status(include_current=True)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=_safe_error_detail(exc)) from exc


@router.post("/seek", response_model=OfflinePlaybackFrameResponse)
def seek_offline_playback(
    request: OfflinePlaybackSeekRequest,
) -> OfflinePlaybackFrameResponse:
    try:
        return offline_playback_service.seek(request.frame_index)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=_safe_error_detail(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=_safe_error_detail(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_safe_error_detail(exc)) from exc


@router.post("/next", response_model=OfflinePlaybackFrameResponse)
def next_offline_playback(
    request: OfflinePlaybackStepRequest,
) -> OfflinePlaybackFrameResponse:
    try:
        return offline_playback_service.next(failures_only=request.failures_only)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=_safe_error_detail(exc)) from exc
    except (IndexError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=_safe_error_detail(exc)) from exc


@router.post("/previous", response_model=OfflinePlaybackFrameResponse)
def previous_offline_playback(
    request: OfflinePlaybackStepRequest,
) -> OfflinePlaybackFrameResponse:
    try:
        return offline_playback_service.previous(failures_only=request.failures_only)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=_safe_error_detail(exc)) from exc
    except (IndexError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=_safe_error_detail(exc)) from exc


@router.get("/frame/{frame_index}/preview.png")
def get_offline_playback_frame_preview(
    frame_index: int,
    max_width: int = Query(default=1200, ge=1, le=4096),
    max_height: int | None = Query(default=None, ge=1, le=4096),
) -> Response:
    try:
        png = offline_playback_service.preview_png(
            frame_index,
            max_width=max_width,
            max_height=max_height,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=_safe_error_detail(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=_safe_error_detail(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_safe_error_detail(exc)) from exc
    return Response(content=png, media_type="image/png")


def _safe_error_detail(exc: Exception) -> str:
    message = str(exc)
    if "/" in message or "\\" in message:
        return "offline playback request failed"
    return message
