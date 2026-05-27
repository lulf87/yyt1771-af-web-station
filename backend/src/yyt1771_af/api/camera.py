from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from yyt1771_af.services.camera_service import (
    CameraOpenResult,
    CameraStatus,
    camera_service,
)

router = APIRouter(prefix="/camera", tags=["camera"])


class CameraOpenRequest(BaseModel):
    profile: str = "dev_mock"


class CameraCloseResponse(BaseModel):
    opened: bool


@router.post("/open", response_model=CameraOpenResult)
def open_camera(request: CameraOpenRequest) -> CameraOpenResult:
    try:
        return camera_service.open(request.profile)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/close", response_model=CameraCloseResponse)
def close_camera() -> CameraCloseResponse:
    camera_service.close()
    return CameraCloseResponse(opened=False)


@router.get("/status", response_model=CameraStatus)
def get_camera_status() -> CameraStatus:
    return camera_service.status()


@router.get("/frame/{frame_id}/preview.svg")
def get_frame_preview(frame_id: int) -> Response:
    try:
        svg = camera_service.preview_svg(frame_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=svg, media_type="image/svg+xml")
