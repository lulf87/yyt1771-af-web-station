from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse

from yyt1771_af.services.offline_datasets import (
    OfflineDatasetInfo,
    list_offline_dataset_infos,
)
from yyt1771_af.services.offline_run_service import (
    OfflineRunCloseResponse,
    OfflineRunErrorResponse,
    OfflineRunFrameResponse,
    OfflineRunOpenRequest,
    OfflineRunOpenResponse,
    OfflineRunRequestError,
    OfflineRunSeekRequest,
    OfflineRunStatusResponse,
    OfflineRunTraceResponse,
    offline_run_service,
)

router = APIRouter(prefix="/offline-run", tags=["offline-run"])


@router.get("/datasets", response_model=list[OfflineDatasetInfo])
def list_offline_datasets() -> list[OfflineDatasetInfo]:
    return list_offline_dataset_infos()


@router.post("/open", response_model=OfflineRunOpenResponse)
def open_offline_run(request: OfflineRunOpenRequest) -> OfflineRunOpenResponse:
    try:
        return offline_run_service.open(request)
    except OfflineRunRequestError as exc:
        return _offline_run_error_response(exc)
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=_safe_error_detail(exc)) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=_safe_error_detail(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=_safe_error_detail(exc)) from exc


@router.get("/{session_id}/status", response_model=OfflineRunStatusResponse)
def get_offline_run_status(session_id: str) -> OfflineRunStatusResponse:
    try:
        return offline_run_service.status(session_id)
    except OfflineRunRequestError as exc:
        return _offline_run_error_response(exc)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=_safe_error_detail(exc)) from exc


@router.post("/{session_id}/status", response_model=OfflineRunStatusResponse)
def post_offline_run_status(session_id: str) -> OfflineRunStatusResponse:
    return get_offline_run_status(session_id)


@router.post("/{session_id}/next", response_model=OfflineRunFrameResponse)
def next_offline_run(session_id: str) -> OfflineRunFrameResponse:
    try:
        return offline_run_service.next(session_id)
    except OfflineRunRequestError as exc:
        return _offline_run_error_response(exc)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=_safe_error_detail(exc)) from exc
    except (IndexError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=_safe_error_detail(exc)) from exc


@router.post("/{session_id}/inspect", response_model=OfflineRunFrameResponse)
def inspect_offline_run(session_id: str) -> OfflineRunFrameResponse:
    try:
        return offline_run_service.inspect(session_id)
    except OfflineRunRequestError as exc:
        return _offline_run_error_response(exc)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=_safe_error_detail(exc)) from exc
    except (IndexError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=_safe_error_detail(exc)) from exc


@router.post("/{session_id}/previous", response_model=OfflineRunFrameResponse)
def previous_offline_run(session_id: str) -> OfflineRunFrameResponse:
    try:
        return offline_run_service.previous(session_id)
    except OfflineRunRequestError as exc:
        return _offline_run_error_response(exc)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=_safe_error_detail(exc)) from exc
    except (IndexError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=_safe_error_detail(exc)) from exc


@router.post("/{session_id}/seek", response_model=OfflineRunFrameResponse)
def seek_offline_run(
    session_id: str,
    request: OfflineRunSeekRequest,
) -> OfflineRunFrameResponse:
    try:
        return offline_run_service.seek(session_id, request.frame_index)
    except OfflineRunRequestError as exc:
        return _offline_run_error_response(exc)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=_safe_error_detail(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=_safe_error_detail(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_safe_error_detail(exc)) from exc


@router.post("/{session_id}/close", response_model=OfflineRunCloseResponse)
def close_offline_run(session_id: str) -> OfflineRunCloseResponse:
    try:
        return offline_run_service.close(session_id)
    except OfflineRunRequestError as exc:
        return _offline_run_error_response(exc)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=_safe_error_detail(exc)) from exc


@router.get("/{session_id}/frame/{frame_index}/preview.png")
def get_offline_run_frame_preview(
    session_id: str,
    frame_index: int,
    max_width: int = Query(default=1200, ge=1, le=4096),
    max_height: int | None = Query(default=None, ge=1, le=4096),
) -> Response:
    try:
        png = offline_run_service.preview_png(
            session_id,
            frame_index,
            max_width=max_width,
            max_height=max_height,
        )
    except OfflineRunRequestError as exc:
        return _offline_run_error_response(exc)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=_safe_error_detail(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=_safe_error_detail(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_safe_error_detail(exc)) from exc
    return Response(content=png, media_type="image/png")


@router.get("/{session_id}/trace", response_model=OfflineRunTraceResponse)
def get_offline_run_trace(session_id: str) -> OfflineRunTraceResponse:
    try:
        return offline_run_service.trace(session_id)
    except OfflineRunRequestError as exc:
        return _offline_run_error_response(exc)


def _offline_run_error_response(exc: OfflineRunRequestError) -> JSONResponse:
    payload: OfflineRunErrorResponse = exc.to_response()
    return JSONResponse(
        status_code=exc.status_code,
        content=payload.model_dump(mode="json"),
    )


def _safe_error_detail(exc: Exception) -> str:
    message = str(exc)
    if "/" in message or "\\" in message:
        return "offline run request failed"
    return message
