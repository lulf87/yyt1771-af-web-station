from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal
from uuid import uuid4

import numpy as np
from pydantic import BaseModel

from yyt1771_af.core.config import load_detector_recipe_config
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
from yyt1771_af.report.debug_overlay import render_detection_debug_overlay_png
from yyt1771_af.services.camera_service import CameraService, camera_service
from yyt1771_af.vision.detection import detect_target
from yyt1771_af.vision.roi_ops import rotated_roi_mask
from yyt1771_af.vision.segmentation import (
    connected_components,
    contour_mask,
    fill_internal_holes,
    segment_target_mask_layers_debug,
)


@dataclass(frozen=True, slots=True)
class DebugOverlayArtifact:
    frame_ref: FrameRef
    roi: RotatedRoi
    detection: DetectionResult
    raw_foreground_mask: np.ndarray | None
    morphology_foreground_mask: np.ndarray | None
    filled_envelope_mask: np.ndarray | None
    selected_component_mask: np.ndarray | None
    selected_contour_mask: np.ndarray | None


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
    segmentation: SegmentationParams | None = None


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
    debug_overlay_url: str | None = None


class SetupConfirmRequest(BaseModel):
    name: str
    target_family: TargetFamily
    roi: RotatedRoi
    recipe_name: str
    segmentation: SegmentationParams | None = None


class SetupConfirmResponse(BaseModel):
    measurement_definition_id: str
    saved: bool
    measurement_definition: MeasurementDefinition


class SetupService:
    def __init__(self, camera: CameraService) -> None:
        self._camera = camera
        self._frozen_frame_ref: FrameRef | None = None
        self._measurement_definitions: dict[str, MeasurementDefinition] = {}
        self._debug_artifacts: dict[str, DebugOverlayArtifact] = {}

    def freeze(self, request: FreezeRequest) -> FreezeResponse:
        if request.source != "latest":
            raise ValueError("only latest frame freezing is supported")

        frame = self._camera.current_frame()
        frame_ref = self._camera.frame_ref(frame)
        self._frozen_frame_ref = frame_ref
        self._camera.pin_frame(frame.frame_id)
        return FreezeResponse(
            frame_ref=frame_ref,
            preview_url=f"/api/camera/frame/{frame.frame_id}/preview.png?max_width=1200",
        )

    def detect(self, request: SetupDetectRequest) -> SetupDetectResponse:
        frame = self._camera.get_frame(request.frame_ref)
        segmentation = request.segmentation or _segmentation_for_target(
            request.target_family,
            request.recipe_name,
        )
        detector_params = _detector_params_for_target(request.target_family, request.recipe_name)
        result = detect_target(
            frame=frame.image,
            roi=request.roi,
            target_family=request.target_family,
            segmentation=segmentation,
            params=detector_params,
        )
        debug_id = f"dbg_{uuid4().hex[:12]}"
        self._debug_artifacts[debug_id] = _build_debug_artifact(
            frame_ref=request.frame_ref,
            frame_image=frame.image,
            roi=request.roi,
            target_family=request.target_family,
            segmentation=segmentation,
            detector_params=detector_params,
            detection=result,
        )
        self._trim_debug_artifacts()
        return _serialize_detection_result(
            result,
            debug_overlay_url=f"/api/setup/debug-overlay/{debug_id}.png?max_width=1200",
        )

    def confirm(self, request: SetupConfirmRequest) -> SetupConfirmResponse:
        frame = self._camera.current_frame()
        measurement_definition = MeasurementDefinition(
            measurement_definition_id=f"md_{uuid4().hex[:12]}",
            name=request.name,
            target_family=request.target_family,
            roi=request.roi,
            recipe_name=request.recipe_name,
            segmentation=request.segmentation,
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

    def debug_overlay_png(
        self,
        debug_id: str,
        *,
        max_width: int,
        max_height: int | None = None,
        show_raw_foreground: bool = True,
        show_morphology_foreground: bool = True,
        show_filled_envelope: bool = True,
        show_selected_contour: bool = True,
        show_rejected_candidates: bool = True,
    ) -> bytes:
        artifact = self._debug_artifacts.get(debug_id)
        if artifact is None:
            raise KeyError(f"debug overlay {debug_id} is not available")
        frame = self._camera.get_frame(artifact.frame_ref)
        return render_detection_debug_overlay_png(
            frame=frame.image,
            roi=artifact.roi,
            detection=artifact.detection,
            raw_foreground_mask=artifact.raw_foreground_mask,
            morphology_foreground_mask=artifact.morphology_foreground_mask,
            filled_envelope_mask=artifact.filled_envelope_mask,
            selected_component_mask=artifact.selected_component_mask,
            selected_contour_mask=artifact.selected_contour_mask,
            max_width=max_width,
            max_height=max_height,
            show_raw_foreground=show_raw_foreground,
            show_morphology_foreground=show_morphology_foreground,
            show_filled_envelope=show_filled_envelope,
            show_selected_contour=show_selected_contour,
            show_rejected_candidates=show_rejected_candidates,
        )

    def _trim_debug_artifacts(self) -> None:
        while len(self._debug_artifacts) > 4:
            first_key = next(iter(self._debug_artifacts))
            self._debug_artifacts.pop(first_key, None)


def _segmentation_for_target(
    target_family: TargetFamily,
    recipe_name: str | None = None,
) -> SegmentationParams:
    return load_detector_recipe_config(target_family, recipe_name).segmentation


def _detector_params_for_target(
    target_family: TargetFamily,
    recipe_name: str | None = None,
) -> BalloonEnvelopeDetectorParams | WireStripDetectorParams:
    return load_detector_recipe_config(target_family, recipe_name).detector


def _serialize_detection_result(
    result: DetectionResult,
    *,
    debug_overlay_url: str | None = None,
) -> SetupDetectResponse:
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
        debug_overlay_url=debug_overlay_url,
    )


def _build_debug_artifact(
    *,
    frame_ref: FrameRef,
    frame_image: np.ndarray,
    roi: RotatedRoi,
    target_family: TargetFamily,
    segmentation: SegmentationParams,
    detector_params: BalloonEnvelopeDetectorParams | WireStripDetectorParams,
    detection: DetectionResult,
) -> DebugOverlayArtifact:
    try:
        roi_mask = rotated_roi_mask(frame_image.shape, roi)
        layers, _, _ = segment_target_mask_layers_debug(
            frame_image,
            roi_mask,
            segmentation,
            preferred_point_xy=(roi.center_x, roi.center_y),
        )
        filled_envelope = fill_internal_holes(layers.morphology_foreground) & roi_mask
        fill_internal_holes_used = (
            detector_params.fill_internal_holes
            if (
                target_family is TargetFamily.BALLOON_ENVELOPE
                and isinstance(detector_params, BalloonEnvelopeDetectorParams)
            )
            else False
        )
        if segmentation.fill_internal_holes is not None:
            fill_internal_holes_used = segmentation.fill_internal_holes
        foreground = filled_envelope if fill_internal_holes_used else layers.morphology_foreground
        components = connected_components(foreground, segmentation.min_component_area_px)
        selected_component_mask = components[0].mask if components else None
        selected_contour_mask = (
            contour_mask(selected_component_mask) if selected_component_mask is not None else None
        )
    except ValueError:
        layers = None
        filled_envelope = None
        selected_component_mask = None
        selected_contour_mask = None
    return DebugOverlayArtifact(
        frame_ref=frame_ref,
        roi=roi,
        detection=detection,
        raw_foreground_mask=layers.raw_foreground if layers is not None else None,
        morphology_foreground_mask=layers.morphology_foreground if layers is not None else None,
        filled_envelope_mask=filled_envelope,
        selected_component_mask=selected_component_mask,
        selected_contour_mask=selected_contour_mask,
    )


setup_service = SetupService(camera_service)
