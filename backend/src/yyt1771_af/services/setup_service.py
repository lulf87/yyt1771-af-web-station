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
    DetectorParams,
    FrameIdentity,
    FrameRef,
    MeasurementDefinition,
    Point2D,
    PointProbeResponse,
    RotatedRoi,
    SegmentationParams,
    WireStripDetectorParams,
)
from yyt1771_af.core.statuses import TargetFamily
from yyt1771_af.report.debug_overlay import render_detection_debug_overlay_png
from yyt1771_af.report.roi_crop import render_roi_crop_png
from yyt1771_af.services.camera_service import CameraService, camera_service
from yyt1771_af.services.frame_identity import frame_identity, recipe_summary
from yyt1771_af.vision.detection import detect_target
from yyt1771_af.vision.roi_ops import rotated_roi_mask
from yyt1771_af.vision.segmentation import (
    connected_components,
    contour_mask,
    fill_internal_holes,
    segment_target_mask_layers_debug,
)
from yyt1771_af.vision.wire_auto_tune import auto_tune_wire_threshold
from yyt1771_af.vision.wire_filtering import analyze_wire_components
from yyt1771_af.vision.wire_point_probe import (
    probe_wire_point,
    wire_component_diagnostics,
)


@dataclass(frozen=True, slots=True)
class DebugOverlayArtifact:
    frame_ref: FrameRef
    frame_identity: FrameIdentity
    roi: RotatedRoi
    detection: DetectionResult
    raw_foreground_mask: np.ndarray | None
    morphology_foreground_mask: np.ndarray | None
    filled_envelope_mask: np.ndarray | None
    selected_component_mask: np.ndarray | None
    rejected_component_mask: np.ndarray | None
    selected_contour_mask: np.ndarray | None
    wire_components: list[object] | None = None


class FreezeRequest(BaseModel):
    source: Literal["latest"] = "latest"


class FreezeResponse(BaseModel):
    frame_ref: FrameRef
    preview_url: str
    frame_identity: FrameIdentity


class SetupDetectRequest(BaseModel):
    frame_ref: FrameRef
    roi: RotatedRoi
    target_family: TargetFamily
    recipe_name: str
    segmentation: SegmentationParams | None = None
    detector: DetectorParams | None = None


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
    roi_crop_url: str | None = None
    frame_ref: FrameRef | None = None
    frame_identity: FrameIdentity | None = None


class SetupPointProbeRequest(SetupDetectRequest):
    x: float
    y: float
    coordinate_space: Literal["acquisition"] = "acquisition"


class SetupConfirmRequest(BaseModel):
    name: str
    target_family: TargetFamily
    roi: RotatedRoi
    recipe_name: str
    segmentation: SegmentationParams | None = None
    detector: DetectorParams | None = None
    auto_tuned: bool = False
    auto_tune_score: float | None = None


class SetupConfirmResponse(BaseModel):
    measurement_definition_id: str
    saved: bool
    measurement_definition: MeasurementDefinition


class WireAutoTuneRequest(BaseModel):
    frame_ref: FrameRef
    roi: RotatedRoi
    recipe_name: str
    target_family: TargetFamily = TargetFamily.WIRE_STRIP
    segmentation: SegmentationParams | None = None
    detector: DetectorParams | None = None
    candidate_thresholds: list[int] | None = None


class WireAutoTuneCandidateModel(BaseModel):
    threshold_value: int
    status: str
    valid: bool
    formal_ab_span_px: float | None = None
    valid_interval_count: int | None = None
    rejected_interval_count: int
    selected_valid_intervals: list[dict[str, Any]]
    broad_blob_rejection_count: int | None = None
    broad_blob_area_ratio: float | None = None
    local_contrast_score: float | None = None
    wire_likeness_score: float | None = None
    neighbor_line_support: int | None = None
    roi_margin_px: float | None = None
    point_a_on_foreground_boundary: bool | None = None
    point_b_on_foreground_boundary: bool | None = None
    failure_reason: str | None = None
    distance_px: float | None = None
    score: float
    on_stable_platform: bool


class WireAutoTuneResponse(BaseModel):
    target_family: str
    recommended_threshold_value: int | None
    recommended_polarity: str
    recommended_segmentation: SegmentationParams | None
    stable_platform_min: int | None
    stable_platform_max: int | None
    selected_reason: str
    auto_tuned: bool
    candidates: list[WireAutoTuneCandidateModel]


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
            frame_identity=frame_identity(
                frame=frame,
                source_type=self._camera.status().source_type,
            ),
        )

    def detect(self, request: SetupDetectRequest) -> SetupDetectResponse:
        frame = self._camera.get_frame(request.frame_ref)
        segmentation = request.segmentation or _segmentation_for_target(
            request.target_family,
            request.recipe_name,
        )
        detector_params = _detector_params_for_request(
            request.target_family,
            request.recipe_name,
            request.detector,
        )
        result = detect_target(
            frame=frame.image,
            roi=request.roi,
            target_family=request.target_family,
            segmentation=segmentation,
            params=detector_params,
        )
        result.frame_ref = request.frame_ref
        identity = frame_identity(
            frame=frame,
            source_type=self._camera.status().source_type,
            recipe=recipe_summary(
                target_family=request.target_family,
                recipe_name=request.recipe_name,
                roi=request.roi,
                segmentation=segmentation,
                detector=detector_params,
            ),
            debug_level="full",
        )
        debug_id = f"dbg_{uuid4().hex[:12]}"
        self._debug_artifacts[debug_id] = _build_debug_artifact(
            frame_ref=request.frame_ref,
            frame_identity=identity,
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
            roi_crop_url=f"/api/setup/debug-crop/{debug_id}.png?scale=2",
            frame_identity=identity,
        )

    def probe_point(self, request: SetupPointProbeRequest) -> PointProbeResponse:
        if request.coordinate_space != "acquisition":
            raise ValueError("probe point must be in acquisition coordinates")
        frame = self._camera.get_frame(request.frame_ref)
        segmentation = request.segmentation or _segmentation_for_target(
            request.target_family,
            request.recipe_name,
        )
        detector_params = _detector_params_for_request(
            request.target_family,
            request.recipe_name,
            request.detector,
        )
        if request.target_family is not TargetFamily.WIRE_STRIP or not isinstance(
            detector_params, WireStripDetectorParams
        ):
            raise ValueError("point probe is only available for wire_strip")
        identity = frame_identity(
            frame=frame,
            source_type=self._camera.status().source_type,
            recipe=recipe_summary(
                target_family=request.target_family,
                recipe_name=request.recipe_name,
                roi=request.roi,
                segmentation=segmentation,
                detector=detector_params,
            ),
            debug_level="full",
        )
        return probe_wire_point(
            frame=frame.image,
            roi=request.roi,
            segmentation=segmentation,
            params=detector_params,
            point=Point2D(x=request.x, y=request.y),
            identity=identity,
        )

    def auto_tune_wire(self, request: WireAutoTuneRequest) -> WireAutoTuneResponse:
        if request.target_family is not TargetFamily.WIRE_STRIP:
            raise ValueError("wire auto tune is only available for the wire_strip target family")
        frame = self._camera.get_frame(request.frame_ref)
        base_segmentation = request.segmentation or _segmentation_for_target(
            TargetFamily.WIRE_STRIP,
            request.recipe_name,
        )
        detector_params = _detector_params_for_request(
            TargetFamily.WIRE_STRIP,
            request.recipe_name,
            request.detector,
        )
        if not isinstance(detector_params, WireStripDetectorParams):
            raise ValueError("wire auto tune requires wire_strip detector params")
        result = auto_tune_wire_threshold(
            frame=frame.image,
            roi=request.roi,
            base_segmentation=base_segmentation,
            detector_params=detector_params,
            candidate_thresholds=request.candidate_thresholds,
        )
        recommended_segmentation: SegmentationParams | None = None
        if result.recommended_threshold_value is not None:
            recommended_segmentation = base_segmentation.model_copy(
                update={
                    "threshold_mode": "fixed",
                    "threshold_value": result.recommended_threshold_value,
                }
            )
        return WireAutoTuneResponse(
            target_family=TargetFamily.WIRE_STRIP.value,
            recommended_threshold_value=result.recommended_threshold_value,
            recommended_polarity=result.recommended_polarity,
            recommended_segmentation=recommended_segmentation,
            stable_platform_min=result.stable_platform_min,
            stable_platform_max=result.stable_platform_max,
            selected_reason=result.selected_reason,
            auto_tuned=result.auto_tuned,
            candidates=[
                WireAutoTuneCandidateModel(
                    threshold_value=candidate.threshold_value,
                    status=candidate.status,
                    valid=candidate.valid,
                    formal_ab_span_px=candidate.formal_ab_span_px,
                    valid_interval_count=candidate.valid_interval_count,
                    rejected_interval_count=candidate.rejected_interval_count,
                    selected_valid_intervals=candidate.selected_valid_intervals,
                    broad_blob_rejection_count=candidate.broad_blob_rejection_count,
                    broad_blob_area_ratio=candidate.broad_blob_area_ratio,
                    local_contrast_score=candidate.local_contrast_score,
                    wire_likeness_score=candidate.wire_likeness_score,
                    neighbor_line_support=candidate.neighbor_line_support,
                    roi_margin_px=candidate.roi_margin_px,
                    point_a_on_foreground_boundary=candidate.point_a_on_foreground_boundary,
                    point_b_on_foreground_boundary=candidate.point_b_on_foreground_boundary,
                    failure_reason=candidate.failure_reason,
                    distance_px=candidate.distance_px,
                    score=candidate.score,
                    on_stable_platform=candidate.on_stable_platform,
                )
                for candidate in result.candidates
            ],
        )

    def confirm(self, request: SetupConfirmRequest) -> SetupConfirmResponse:
        frame = self._camera.current_frame()
        segmentation = request.segmentation or _segmentation_for_target(
            request.target_family,
            request.recipe_name,
        )
        detector_params = _detector_params_for_request(
            request.target_family,
            request.recipe_name,
            request.detector,
        )
        measurement_definition = MeasurementDefinition(
            measurement_definition_id=f"md_{uuid4().hex[:12]}",
            name=request.name,
            target_family=request.target_family,
            roi=request.roi,
            recipe_name=request.recipe_name,
            segmentation=segmentation,
            detector=detector_params,
            detector_version="v1",
            acquisition_frame_size=AcquisitionFrameSize(width=frame.width, height=frame.height),
            created_at_ms=time.time_ns() // 1_000_000,
            auto_tuned=request.auto_tuned,
            auto_tune_score=request.auto_tune_score,
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
            frame_identity=artifact.frame_identity,
            raw_foreground_mask=artifact.raw_foreground_mask,
            morphology_foreground_mask=artifact.morphology_foreground_mask,
            filled_envelope_mask=artifact.filled_envelope_mask,
            selected_component_mask=artifact.selected_component_mask,
            rejected_component_mask=artifact.rejected_component_mask,
            selected_contour_mask=artifact.selected_contour_mask,
            wire_components=artifact.wire_components,
            max_width=max_width,
            max_height=max_height,
            show_raw_foreground=show_raw_foreground,
            show_morphology_foreground=show_morphology_foreground,
            show_filled_envelope=show_filled_envelope,
            show_selected_contour=show_selected_contour,
            show_rejected_candidates=show_rejected_candidates,
        )

    def debug_crop_png(self, debug_id: str, *, scale: int = 1) -> bytes:
        artifact = self._debug_artifacts.get(debug_id)
        if artifact is None:
            raise KeyError(f"debug crop {debug_id} is not available")
        frame = self._camera.get_frame(artifact.frame_ref)
        return render_roi_crop_png(frame=frame.image, roi=artifact.roi, scale=scale)

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


def _detector_params_for_request(
    target_family: TargetFamily,
    recipe_name: str | None,
    detector: DetectorParams | None,
) -> BalloonEnvelopeDetectorParams | WireStripDetectorParams:
    detector_params = detector or _detector_params_for_target(target_family, recipe_name)
    expected_kind = _detector_params_for_target(target_family, recipe_name).detector_kind
    if detector_params.detector_kind is not expected_kind:
        raise ValueError("detector params do not match target_family")
    return detector_params


def _serialize_detection_result(
    result: DetectionResult,
    *,
    debug_overlay_url: str | None = None,
    roi_crop_url: str | None = None,
    frame_identity: FrameIdentity | None = None,
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
        roi_crop_url=roi_crop_url,
        frame_ref=result.frame_ref,
        frame_identity=frame_identity,
    )


def _build_debug_artifact(
    *,
    frame_ref: FrameRef,
    frame_identity: FrameIdentity,
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
        contact_source = (
            detector_params.contact_source
            if (
                target_family is TargetFamily.BALLOON_ENVELOPE
                and isinstance(detector_params, BalloonEnvelopeDetectorParams)
            )
            else "bridged_foreground"
        )
        if contact_source == "raw_foreground":
            foreground = layers.raw_foreground
        elif contact_source == "filled_envelope":
            foreground = filled_envelope
        else:
            foreground = layers.morphology_foreground
        components = connected_components(foreground, segmentation.min_component_area_px)
        rejected_component_mask: np.ndarray | None = None
        wire_components = None
        if target_family is TargetFamily.WIRE_STRIP and isinstance(
            detector_params, WireStripDetectorParams
        ):
            wire_analysis = analyze_wire_components(
                image=frame_image,
                roi=roi,
                roi_mask=roi_mask,
                foreground=foreground,
                components=components,
                params=detector_params,
            )
            selected_component_mask = wire_analysis.wire_foreground
            rejected_component_mask = np.zeros_like(foreground, dtype=bool)
            for component, metric in zip(components, wire_analysis.metrics, strict=False):
                if not metric.accepted:
                    rejected_component_mask |= component.mask
            wire_components = wire_component_diagnostics(wire_analysis)
        elif (
            target_family is TargetFamily.BALLOON_ENVELOPE
            and isinstance(detector_params, BalloonEnvelopeDetectorParams)
            and detector_params.envelope_mode == "open_mesh"
            and components
        ):
            selected_component_mask = np.zeros_like(foreground, dtype=bool)
            for component in components:
                selected_component_mask |= component.mask
        else:
            selected_component_mask = components[0].mask if components else None
        selected_contour_mask = (
            contour_mask(selected_component_mask) if selected_component_mask is not None else None
        )
    except ValueError:
        layers = None
        filled_envelope = None
        selected_component_mask = None
        rejected_component_mask = None
        selected_contour_mask = None
        wire_components = None
    return DebugOverlayArtifact(
        frame_ref=frame_ref,
        frame_identity=frame_identity,
        roi=roi,
        detection=detection,
        raw_foreground_mask=layers.raw_foreground if layers is not None else None,
        morphology_foreground_mask=layers.morphology_foreground if layers is not None else None,
        filled_envelope_mask=filled_envelope,
        selected_component_mask=selected_component_mask,
        rejected_component_mask=rejected_component_mask,
        selected_contour_mask=selected_contour_mask,
        wire_components=wire_components,
    )


setup_service = SetupService(camera_service)
