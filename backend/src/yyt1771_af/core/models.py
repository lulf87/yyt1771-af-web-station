from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

import numpy as np
from pydantic import BaseModel, Field, field_validator, model_validator

from yyt1771_af.core.statuses import (
    AnalysisMethod,
    AnalysisStatus,
    CoordinateSpace,
    DetectionStatus,
    DetectorKind,
    TargetFamily,
    TemperatureStatus,
)


class Point2D(BaseModel):
    x: float
    y: float
    coordinate_space: CoordinateSpace = CoordinateSpace.ACQUISITION


class RotatedRoi(BaseModel):
    center_x: float
    center_y: float
    width: float = Field(gt=0.0)
    height: float = Field(gt=0.0)
    angle_deg: float
    coordinate_space: CoordinateSpace = CoordinateSpace.ACQUISITION

    @field_validator("coordinate_space")
    @classmethod
    def require_acquisition_coordinates(cls, value: CoordinateSpace) -> CoordinateSpace:
        if value is not CoordinateSpace.ACQUISITION:
            raise ValueError("formal ROI must be in acquisition coordinates")
        return value


class FrameRef(BaseModel):
    frame_id: int
    timestamp_ms: int
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    coordinate_space: CoordinateSpace = CoordinateSpace.ACQUISITION

    @field_validator("coordinate_space")
    @classmethod
    def require_acquisition_coordinates(cls, value: CoordinateSpace) -> CoordinateSpace:
        if value is not CoordinateSpace.ACQUISITION:
            raise ValueError("frame references must be in acquisition coordinates")
        return value


@dataclass(frozen=True, slots=True)
class Frame:
    frame_id: int
    timestamp_ms: int
    width: int
    height: int
    coordinate_space: CoordinateSpace
    image: np.ndarray


class SegmentationParams(BaseModel):
    polarity: Literal["dark_on_light", "light_on_dark", "auto"] = "auto"
    threshold_mode: Literal["otsu", "adaptive", "fixed"] = "otsu"
    threshold_value: int | None = Field(default=None, ge=0, le=255)
    blur_kernel: int = Field(default=3, gt=0)
    close_kernel: int = Field(default=5, gt=0)
    open_kernel: int = Field(default=3, gt=0)
    min_component_area_px: int = Field(default=50, gt=0)


class BalloonEnvelopeDetectorParams(BaseModel):
    detector_kind: Literal[DetectorKind.BALLOON_ENVELOPE_DETECTOR] = (
        DetectorKind.BALLOON_ENVELOPE_DETECTOR
    )
    min_quality: float = Field(default=0.65, ge=0.0, le=1.0)
    max_point_jump_px: float | None = Field(default=25.0, gt=0.0)
    reject_contact_on_roi_boundary: bool = True
    boundary_margin_px: float = Field(default=4.0, ge=0.0)
    ignore_internal_texture: bool = True
    fill_internal_holes: bool = True
    bridge_mesh_gaps: bool = True


class WireStripDetectorParams(BaseModel):
    detector_kind: Literal[DetectorKind.WIRE_STRIP_DETECTOR] = DetectorKind.WIRE_STRIP_DETECTOR
    min_quality: float = Field(default=0.60, ge=0.0, le=1.0)
    max_point_jump_px: float | None = Field(default=20.0, gt=0.0)
    reject_contact_on_roi_boundary: bool = True
    boundary_margin_px: float = Field(default=3.0, ge=0.0)
    require_physical_endpoints: Literal[False] = False
    skeleton_endpoint_detection: Literal[False] = False
    preserve_visible_strip_contour: bool = True


class BalloonEnvelopeRecipe(BaseModel):
    name: str
    target_family: Literal[TargetFamily.BALLOON_ENVELOPE] = TargetFamily.BALLOON_ENVELOPE
    roi: RotatedRoi
    segmentation: SegmentationParams
    detector: BalloonEnvelopeDetectorParams


class WireStripRecipe(BaseModel):
    name: str
    target_family: Literal[TargetFamily.WIRE_STRIP] = TargetFamily.WIRE_STRIP
    roi: RotatedRoi
    segmentation: SegmentationParams
    detector: WireStripDetectorParams


MeasurementRecipe = Annotated[
    BalloonEnvelopeRecipe | WireStripRecipe,
    Field(discriminator="target_family"),
]


class DetectionDiagnostics(BaseModel):
    detector: DetectorKind
    detector_version: str = "v1"
    contour_area_px: float | None = None
    contour_point_count: int | None = None
    candidate_components: int | None = None
    message: str | None = None


class DetectionResult(BaseModel):
    status: DetectionStatus
    valid: bool
    point_a: Point2D | None
    point_b: Point2D | None
    distance_px: float | None
    quality: float = Field(ge=0.0, le=1.0)
    target_family: TargetFamily
    frame_ref: FrameRef | None = None
    diagnostics: DetectionDiagnostics

    @model_validator(mode="after")
    def validate_result_consistency(self) -> DetectionResult:
        expected_detector = {
            TargetFamily.BALLOON_ENVELOPE: DetectorKind.BALLOON_ENVELOPE_DETECTOR,
            TargetFamily.WIRE_STRIP: DetectorKind.WIRE_STRIP_DETECTOR,
        }[self.target_family]
        if self.diagnostics.detector is not expected_detector:
            raise ValueError("diagnostics detector must match target_family")

        if self.valid:
            if self.status is not DetectionStatus.OK:
                raise ValueError("valid detection results must use status ok")
            if self.point_a is None or self.point_b is None or self.distance_px is None:
                raise ValueError(
                    "valid detection results require point_a, point_b, and distance_px"
                )
        else:
            if self.status is DetectionStatus.OK:
                raise ValueError("invalid detection results require a failure status")
            if self.distance_px is not None:
                raise ValueError("invalid detection results must not include distance_px")

        for point_name in ("point_a", "point_b"):
            point = getattr(self, point_name)
            if point is not None and point.coordinate_space is not CoordinateSpace.ACQUISITION:
                raise ValueError(f"{point_name} must be in acquisition coordinates")

        return self


class TemperatureReading(BaseModel):
    timestamp_ms: int
    temperature_c: float | None = None
    status: TemperatureStatus
    source_type: str = "unknown"
    message: str | None = None


class TemperatureControllerSnapshot(BaseModel):
    controller_type: str
    connected: bool
    status: TemperatureStatus
    timestamp_ms: int
    current_temperature_c: float | None = None
    target_temperature_c: float | None = None
    power_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    output_enabled: bool | None = None
    message: str | None = None


class TemperatureCommandResponse(BaseModel):
    status: TemperatureStatus
    ok: bool
    message: str | None = None
    snapshot: TemperatureControllerSnapshot


class TemperatureTargetRequest(BaseModel):
    target_c: float


class TemperaturePowerRequest(BaseModel):
    power_percent: float = Field(ge=0.0, le=100.0)


class TemperatureOutputRequest(BaseModel):
    enabled: bool


class RunSample(BaseModel):
    run_id: str
    sample_index: int
    timestamp_ms: int
    temperature: TemperatureReading | None = None
    temperature_c: float | None = None
    temperature_status: TemperatureStatus = TemperatureStatus.UNAVAILABLE
    detection: DetectionResult


class AcquisitionFrameSize(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class MeasurementDefinition(BaseModel):
    measurement_definition_id: str
    name: str
    target_family: TargetFamily
    roi: RotatedRoi
    recipe_name: str
    detector_version: str = "v1"
    acquisition_frame_size: AcquisitionFrameSize
    coordinate_space: CoordinateSpace = CoordinateSpace.ACQUISITION
    created_at_ms: int

    @field_validator("coordinate_space")
    @classmethod
    def require_acquisition_coordinates(cls, value: CoordinateSpace) -> CoordinateSpace:
        if value is not CoordinateSpace.ACQUISITION:
            raise ValueError("measurement definitions must be in acquisition coordinates")
        return value


class RunDefinition(BaseModel):
    run_id: str
    recipe: MeasurementRecipe
    sample_hz: float = Field(gt=0.0)
    created_at_ms: int
    profile_name: str


class AnalysisCurvePoint(BaseModel):
    sample_index: int
    timestamp_ms: int
    temperature_c: float
    distance_px: float
    recovered_fraction: float = Field(ge=0.0, le=1.0)


class AnalysisResult(BaseModel):
    min_distance_px: float
    max_distance_px: float
    initial_distance_px: float
    final_distance_px: float
    recovered_fraction: float = Field(ge=0.0, le=1.0)
    valid_sample_count: int
    invalid_sample_count: int
    temperature_range: tuple[float, float]
    af95_temperature_c: float | None


class AnalysisResponse(BaseModel):
    method: AnalysisMethod
    status: AnalysisStatus
    curve: list[AnalysisCurvePoint]
    result: AnalysisResult | None
    diagnostics: dict[str, object] = Field(default_factory=dict)
