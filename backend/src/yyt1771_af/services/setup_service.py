from __future__ import annotations

import time
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel

from yyt1771_af.core.models import (
    AcquisitionFrameSize,
    BalloonEnvelopeDetectorParams,
    DetectionResult,
    FrameRef,
    MeasurementDefinition,
    RotatedRoi,
    SegmentationParams,
    WireStripDetectorParams,
)
from yyt1771_af.core.statuses import TargetFamily
from yyt1771_af.services.camera_service import CameraService, camera_service
from yyt1771_af.vision.detection import detect_target


class FreezeRequest(BaseModel):
    source: Literal["latest"] = "latest"


class FreezeResponse(BaseModel):
    frame_ref: FrameRef
    preview_url: str


class SetupDetectRequest(BaseModel):
    frame_ref: FrameRef
    roi: RotatedRoi
    target_family: TargetFamily
    recipe_name: str


class SetupDetectResponse(BaseModel):
    status: str
    valid: bool
    point_a: dict[str, Any] | None
    point_b: dict[str, Any] | None
    distance_px: float | None
    quality: float
    target_family: str
    detector: str
    diagnostics: dict[str, Any]


class SetupConfirmRequest(BaseModel):
    name: str
    target_family: TargetFamily
    roi: RotatedRoi
    recipe_name: str


class SetupConfirmResponse(BaseModel):
    measurement_definition_id: str
    saved: bool
    measurement_definition: MeasurementDefinition


class SetupService:
    def __init__(self, camera: CameraService) -> None:
        self._camera = camera
        self._frozen_frame_ref: FrameRef | None = None
        self._measurement_definitions: dict[str, MeasurementDefinition] = {}

    def freeze(self, request: FreezeRequest) -> FreezeResponse:
        if request.source != "latest":
            raise ValueError("only latest frame freezing is supported")

        frame = self._camera.current_frame()
        frame_ref = self._camera.frame_ref(frame)
        self._frozen_frame_ref = frame_ref
        self._camera.pin_frame(frame.frame_id)
        return FreezeResponse(
            frame_ref=frame_ref,
            preview_url=f"/api/camera/frame/{frame.frame_id}/preview.svg",
        )

    def detect(self, request: SetupDetectRequest) -> SetupDetectResponse:
        frame = self._camera.get_frame(request.frame_ref)
        result = detect_target(
            frame=frame.image,
            roi=request.roi,
            target_family=request.target_family,
            segmentation=_segmentation_for_target(request.target_family),
            params=_detector_params_for_target(request.target_family),
        )
        return _serialize_detection_result(result)

    def confirm(self, request: SetupConfirmRequest) -> SetupConfirmResponse:
        frame = self._camera.current_frame()
        measurement_definition = MeasurementDefinition(
            measurement_definition_id=f"md_{uuid4().hex[:12]}",
            name=request.name,
            target_family=request.target_family,
            roi=request.roi,
            recipe_name=request.recipe_name,
            detector_version="v1",
            acquisition_frame_size=AcquisitionFrameSize(width=frame.width, height=frame.height),
            created_at_ms=time.time_ns() // 1_000_000,
        )
        self._measurement_definitions[measurement_definition.measurement_definition_id] = (
            measurement_definition
        )
        return SetupConfirmResponse(
            measurement_definition_id=measurement_definition.measurement_definition_id,
            saved=True,
            measurement_definition=measurement_definition,
        )

    def get_measurement_definition(self, measurement_definition_id: str) -> MeasurementDefinition:
        measurement_definition = self._measurement_definitions.get(measurement_definition_id)
        if measurement_definition is None:
            raise KeyError(f"measurement definition {measurement_definition_id} is not available")
        return measurement_definition


def _segmentation_for_target(target_family: TargetFamily) -> SegmentationParams:
    if target_family is TargetFamily.BALLOON_ENVELOPE:
        return SegmentationParams(close_kernel=7, open_kernel=1, min_component_area_px=80)
    return SegmentationParams(close_kernel=5, open_kernel=1, min_component_area_px=50)


def _detector_params_for_target(
    target_family: TargetFamily,
) -> BalloonEnvelopeDetectorParams | WireStripDetectorParams:
    if target_family is TargetFamily.BALLOON_ENVELOPE:
        return BalloonEnvelopeDetectorParams()
    return WireStripDetectorParams()


def _serialize_detection_result(result: DetectionResult) -> SetupDetectResponse:
    diagnostics = result.diagnostics.model_dump(mode="json", exclude_none=True)
    detector_kind = diagnostics.pop("detector")
    detector_version = diagnostics.pop("detector_version")
    return SetupDetectResponse(
        status=result.status.value,
        valid=result.valid,
        point_a=result.point_a.model_dump(mode="json") if result.point_a is not None else None,
        point_b=result.point_b.model_dump(mode="json") if result.point_b is not None else None,
        distance_px=result.distance_px,
        quality=result.quality,
        target_family=result.target_family.value,
        detector=f"{detector_kind}:{detector_version}",
        diagnostics=diagnostics,
    )


setup_service = SetupService(camera_service)
