from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from yyt1771_af.core.models import AnalysisResponse
from yyt1771_af.services.analysis_service import analysis_service
from yyt1771_af.services.export_service import ExportPayload, export_service
from yyt1771_af.services.run_service import (
    RunSamplesResponse,
    RunStartRequest,
    RunStartResponse,
    RunStatusResponse,
    RunStopResponse,
    run_service,
)
from yyt1771_af.storage.run_store import run_artifact_store

router = APIRouter(prefix="/runs", tags=["runs"])


class RunListResponse(BaseModel):
    runs: list[dict[str, object]]


@router.get("", response_model=RunListResponse)
def list_runs() -> RunListResponse:
    return RunListResponse(runs=run_artifact_store.list_runs())


@router.post("/start", response_model=RunStartResponse)
def start_run(request: RunStartRequest) -> RunStartResponse:
    try:
        return run_service.start(request)
    except (KeyError, RuntimeError, FileExistsError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{run_id}/status", response_model=RunStatusResponse)
def get_run_status(run_id: str) -> RunStatusResponse:
    try:
        return run_service.status(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{run_id}/stop", response_model=RunStopResponse)
def stop_run(run_id: str) -> RunStopResponse:
    try:
        return run_service.stop(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{run_id}/samples", response_model=RunSamplesResponse)
def get_run_samples(run_id: str) -> RunSamplesResponse:
    try:
        return run_service.samples(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{run_id}/analysis", response_model=AnalysisResponse)
def analyze_run(run_id: str) -> AnalysisResponse:
    try:
        return analysis_service.analyze_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{run_id}/analysis", response_model=AnalysisResponse)
def get_run_analysis(run_id: str) -> AnalysisResponse:
    try:
        return analysis_service.get_analysis(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{run_id}/export.csv")
def export_run_csv(run_id: str) -> Response:
    return _export_response(_export_or_404(run_id, "csv"))


@router.get("/{run_id}/export.json")
def export_run_json(run_id: str) -> Response:
    return _export_response(_export_or_404(run_id, "json"))


@router.get("/{run_id}/export.png")
def export_run_png(run_id: str) -> Response:
    return _export_response(_export_or_404(run_id, "png"))


@router.get("/{run_id}/export.xlsx")
def export_run_xlsx(run_id: str) -> Response:
    return _export_response(_export_or_404(run_id, "xlsx"))


def _export_or_404(run_id: str, export_format: str) -> ExportPayload:
    try:
        if export_format == "csv":
            return export_service.export_csv(run_id)
        if export_format == "json":
            return export_service.export_json(run_id)
        if export_format == "png":
            return export_service.export_png(run_id)
        if export_format == "xlsx":
            return export_service.export_xlsx(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise HTTPException(status_code=404, detail="unsupported export format")


def _export_response(payload: ExportPayload) -> Response:
    return Response(
        content=payload.content,
        media_type=payload.media_type,
        headers={"Content-Disposition": f'attachment; filename="{payload.filename}"'},
    )
