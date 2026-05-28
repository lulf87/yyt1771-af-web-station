from __future__ import annotations

import time
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from yyt1771_af.core.models import (
    DetectionDiagnostics,
    DetectionResult,
    FrameRef,
    MeasurementDefinition,
    RunSample,
)
from yyt1771_af.core.statuses import DetectionStatus
from yyt1771_af.services.camera_service import CameraService, camera_service
from yyt1771_af.services.setup_service import (
    _detector_params_for_target,
    _segmentation_for_target,
    setup_service,
)
from yyt1771_af.services.temperature_service import TemperatureService, temperature_service
from yyt1771_af.storage.run_store import RunArtifactStore, run_artifact_store
from yyt1771_af.vision.detection import detect_target


class RunStartRequest(BaseModel):
    measurement_definition_id: str
    sample_hz: float = Field(gt=0.0)
    sample_count: int = Field(default=10, gt=0, le=1000)


class RunStartResponse(BaseModel):
    run_id: str
    started: bool
    sample_count: int


class RunStatusResponse(BaseModel):
    run_id: str
    status: Literal["running", "stopped"]
    sample_hz: float
    sample_count: int
    measurement_definition_id: str
    temperature_source: dict[str, Any]


class RunStopResponse(BaseModel):
    run_id: str
    stopped: bool


class RunSamplesResponse(BaseModel):
    run_id: str
    samples: list[dict[str, Any]]


class RunService:
    def __init__(
        self,
        *,
        camera: CameraService,
        store: RunArtifactStore,
        temperature: TemperatureService,
    ) -> None:
        self._camera = camera
        self._store = store
        self._temperature = temperature
        self._runs: dict[str, dict[str, Any]] = {}

    def start(self, request: RunStartRequest) -> RunStartResponse:
        measurement_definition = setup_service.get_measurement_definition(
            request.measurement_definition_id
        )
        run_id = f"run_{uuid4().hex[:12]}"
        created_at_ms = time.time_ns() // 1_000_000
        self._store.create_run_dir(run_id)
        metadata: dict[str, Any] = {
            "run_id": run_id,
            "status": "running",
            "sample_hz": request.sample_hz,
            "sample_count": 0,
            "measurement_definition_id": measurement_definition.measurement_definition_id,
            "created_at_ms": created_at_ms,
            "source_type": self._camera.status().source_type,
            "temperature_source": self._temperature.metadata(),
        }
        self._store.write_metadata(run_id, metadata)
        self._store.write_measurement_definition(run_id, measurement_definition)
        self._runs[run_id] = metadata

        interval_seconds = 1.0 / request.sample_hz
        next_sample_time = time.monotonic()
        for sample_index in range(request.sample_count):
            if sample_index > 0:
                sleep_seconds = next_sample_time - time.monotonic()
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
            sample = self._capture_sample(run_id, sample_index, measurement_definition)
            self._store.append_sample(sample)
            next_sample_time = time.monotonic() + interval_seconds

        metadata["sample_count"] = request.sample_count
        self._store.write_metadata(run_id, metadata)
        return RunStartResponse(run_id=run_id, started=True, sample_count=request.sample_count)

    def status(self, run_id: str) -> RunStatusResponse:
        metadata = self._metadata_for_run(run_id)
        return RunStatusResponse(
            run_id=run_id,
            status=metadata["status"],
            sample_hz=metadata["sample_hz"],
            sample_count=metadata["sample_count"],
            measurement_definition_id=metadata["measurement_definition_id"],
            temperature_source=metadata["temperature_source"],
        )

    def stop(self, run_id: str) -> RunStopResponse:
        metadata = self._metadata_for_run(run_id)
        metadata["status"] = "stopped"
        self._store.write_metadata(run_id, metadata)
        return RunStopResponse(run_id=run_id, stopped=True)

    def samples(self, run_id: str) -> RunSamplesResponse:
        self._metadata_for_run(run_id)
        return RunSamplesResponse(run_id=run_id, samples=self._store.read_samples(run_id))

    def _capture_sample(
        self,
        run_id: str,
        sample_index: int,
        measurement_definition: MeasurementDefinition,
    ) -> RunSample:
        frame = self._camera.get_latest_frame()
        frame_ref = FrameRef(
            frame_id=frame.frame_id,
            timestamp_ms=frame.timestamp_ms,
            width=frame.width,
            height=frame.height,
        )
        if (
            frame.width != measurement_definition.acquisition_frame_size.width
            or frame.height != measurement_definition.acquisition_frame_size.height
        ):
            detection = DetectionResult(
                status=DetectionStatus.STALE_FRAME_GEOMETRY_MISMATCH,
                valid=False,
                point_a=None,
                point_b=None,
                distance_px=None,
                quality=0.0,
                target_family=measurement_definition.target_family,
                frame_ref=frame_ref,
                diagnostics=DetectionDiagnostics(
                    detector=_detector_params_for_target(
                        measurement_definition.target_family,
                        measurement_definition.recipe_name,
                    ).detector_kind,
                    message="Frame dimensions differ from the confirmed measurement definition.",
                ),
            )
        else:
            detection = detect_target(
                frame=frame.image,
                roi=measurement_definition.roi,
                target_family=measurement_definition.target_family,
                segmentation=measurement_definition.segmentation
                or _segmentation_for_target(
                    measurement_definition.target_family,
                    measurement_definition.recipe_name,
                ),
                params=_detector_params_for_target(
                    measurement_definition.target_family,
                    measurement_definition.recipe_name,
                ),
            )
            detection.frame_ref = frame_ref

        temperature = self._temperature.read_current_temperature()
        return RunSample(
            run_id=run_id,
            sample_index=sample_index,
            timestamp_ms=frame.timestamp_ms,
            temperature=temperature,
            temperature_c=temperature.temperature_c,
            temperature_status=temperature.status,
            detection=detection,
        )

    def _metadata_for_run(self, run_id: str) -> dict[str, Any]:
        metadata = self._runs.get(run_id)
        if metadata is None:
            raise KeyError(f"run {run_id} is not available")
        return metadata


run_service = RunService(
    camera=camera_service,
    store=run_artifact_store,
    temperature=temperature_service,
)
