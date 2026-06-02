from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Literal

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
    frame_name: str | None = None
    frame_index: int | None = None
    dtype: str | None = None


class SegmentationParams(BaseModel):
    polarity: Literal["dark_on_light", "light_on_dark", "auto"] = "auto"
    threshold_mode: Literal["otsu", "adaptive", "fixed"] = "otsu"
    threshold_value: int | None = Field(default=None, ge=0, le=255)
    blur_kernel: int = Field(default=3, gt=0)
    close_kernel: int = Field(default=5, gt=0)
    open_kernel: int = Field(default=3, gt=0)
    min_component_area_px: int = Field(default=50, gt=0)
    fill_internal_holes: bool | None = None


class ComponentBBox(BaseModel):
    min_x: int
    min_y: int
    max_x: int
    max_y: int


class ObjectInterval(BaseModel):
    start_local_x: float
    end_local_x: float
    width_px: float
    line_y: float | None = None
    cluster_id: int | None = None
    gap_to_previous_px: float | None = None
    rejected: bool = False
    reject_reason: str | None = None
    local_contrast_score: float | None = None
    wire_likeness_score: float | None = None
    source_component_id: int | None = None
    touches_roi_boundary: bool | None = None


class WireComponentDiagnostics(BaseModel):
    component_id: int
    area_px: int
    area_ratio_in_roi: float
    bbox: ComponentBBox
    aspect_ratio: float
    orientation_deg: float
    orientation_deviation_deg: float
    local_contrast: float
    wire_likeness_score: float
    accepted: bool
    reject_reason: str | None = None


class FrameIdentity(BaseModel):
    frame_id: int | None = None
    frame_index: int | None = None
    frame_name: str | None = None
    source_type: str
    acquisition_width: int = Field(gt=0)
    acquisition_height: int = Field(gt=0)
    recipe_summary: dict[str, Any] | None = None
    debug_level: str | None = None


class PointProbeResponse(BaseModel):
    frame_identity: FrameIdentity
    x: float
    y: float
    coordinate_space: CoordinateSpace = CoordinateSpace.ACQUISITION
    pixel_value: int | None = None
    inside_roi: bool
    raw_foreground: bool
    morphology_foreground: bool
    wire_foreground: bool
    component_id: int | None = None
    component_accepted: bool | None = None
    component_reject_reason: str | None = None
    interval_id: str | None = None
    selected_valid_interval: bool
    rejected_interval: bool
    rejected_remote_interval: bool
    reject_reason: str | None = None
    source_interval_id: str | None = None
    would_be_ab_source: bool


class BundleClusterDiagnostics(BaseModel):
    cluster_id: int
    interval_count: int
    start_local_x: float
    end_local_x: float
    outer_span_px: float
    total_interval_width_px: float
    support_ratio: float
    max_internal_gap_px: float
    selected: bool = False
    reject_reason: str | None = None


class CandidateLineDiagnostics(BaseModel):
    rank: int | None = None
    selected: bool = False
    measurement_line_y: float
    formal_ab_span_px: float | None = None
    interval_count: int | None = None
    support_ratio: float | None = None
    max_internal_gap_px: float | None = None
    neighbor_line_support: int | None = None
    wire_likeness_score: float | None = None
    rejected_reason: str | None = None
    selected_cluster_id: int | None = None


class BalloonEnvelopeDetectorParams(BaseModel):
    detector_kind: Literal[DetectorKind.BALLOON_ENVELOPE_DETECTOR] = (
        DetectorKind.BALLOON_ENVELOPE_DETECTOR
    )
    envelope_mode: Literal["solid_balloon", "open_mesh"] = "solid_balloon"
    contact_source: Literal["raw_foreground", "bridged_foreground", "filled_envelope"] | None = None
    measurement_model: Literal["blank_object_blank"] = "blank_object_blank"
    min_quality: float = Field(default=0.65, ge=0.0, le=1.0)
    max_point_jump_px: float | None = Field(default=25.0, gt=0.0)
    reject_contact_on_roi_boundary: bool = True
    boundary_margin_px: float = Field(default=4.0, ge=0.0)
    ignore_internal_texture: bool = True
    fill_internal_holes: bool = True
    bridge_mesh_gaps: bool = True

    @model_validator(mode="before")
    @classmethod
    def apply_mode_defaults(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        mode = payload.get("envelope_mode", "solid_balloon")
        if mode == "open_mesh":
            payload.setdefault("contact_source", "bridged_foreground")
            payload.setdefault("fill_internal_holes", False)
        else:
            payload.setdefault("contact_source", "filled_envelope")
            payload.setdefault("fill_internal_holes", True)
        return payload


class WireStripDetectorParams(BaseModel):
    detector_kind: Literal[DetectorKind.WIRE_STRIP_DETECTOR] = DetectorKind.WIRE_STRIP_DETECTOR
    measurement_model: Literal["blank_wire_bundle_envelope_blank"] = (
        "blank_wire_bundle_envelope_blank"
    )
    measurement_mode: Literal["wire_bundle_envelope"] = "wire_bundle_envelope"
    min_quality: float = Field(default=0.60, ge=0.0, le=1.0)
    max_point_jump_px: float | None = Field(default=20.0, gt=0.0)
    reject_contact_on_roi_boundary: bool = True
    boundary_margin_px: float = Field(default=3.0, ge=0.0)
    require_physical_endpoints: Literal[False] = False
    skeleton_endpoint_detection: Literal[False] = False
    preserve_visible_strip_contour: bool = True
    min_interval_width_px: float = Field(default=3.0, ge=0.0)
    max_interval_width_ratio: float = Field(default=0.65, gt=0.0, le=1.0)
    min_valid_interval_count: int = Field(default=2, gt=0)
    min_local_contrast_score: float = Field(default=8.0, ge=0.0)
    min_wire_likeness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    max_broad_blob_area_ratio: float = Field(default=0.22, gt=0.0, le=1.0)
    max_component_area_ratio: float = Field(default=0.45, gt=0.0, le=1.0)
    min_component_area_px: int | None = Field(default=None, gt=0)
    max_internal_gap_px: float | None = Field(default=None, gt=0.0)
    max_internal_gap_ratio: float = Field(default=0.9, gt=0.0, le=1.0)
    max_bundle_internal_gap_px: float | None = Field(default=60.0, gt=0.0)
    max_bundle_internal_gap_ratio: float = Field(default=1.0, gt=0.0, le=1.0)
    min_neighbor_line_support: int = Field(default=1, ge=0)
    min_support_ratio: float = Field(default=0.08, ge=0.0, le=1.0)
    span_tie_tolerance_px: float = Field(default=2.0, ge=0.0)
    component_aspect_ratio_min: float = Field(default=1.8, ge=1.0)
    broad_blob_max_aspect_ratio: float = Field(default=1.8, ge=1.0)
    enable_broad_blob_rejection: bool = True
    enable_local_contrast_filter: bool = True
    enable_neighbor_line_support_filter: bool = True
    enable_remote_interval_rejection: bool = True
    enable_orientation_scoring: bool = True


DetectorParams = Annotated[
    BalloonEnvelopeDetectorParams | WireStripDetectorParams,
    Field(discriminator="detector_kind"),
]


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
    envelope_mode: str | None = None
    configured_contact_source: str | None = None
    contact_source_used: str | None = None
    actual_contact_source_area_ratio: float | None = None
    threshold_mode: str | None = None
    configured_polarity: str | None = None
    close_kernel: int | None = None
    open_kernel: int | None = None
    min_component_area_px: int | None = None
    contour_area_px: float | None = None
    contour_point_count: int | None = None
    candidate_components: int | None = None
    threshold_value: int | None = None
    selected_polarity: str | None = None
    selected_reason: str | None = None
    contrast: float | None = None
    dark_area_ratio: float | None = None
    light_area_ratio: float | None = None
    preferred_point_xy: Point2D | None = None
    preferred_point_hit_dark: bool | None = None
    preferred_point_hit_light: bool | None = None
    raw_foreground_area_px: int | None = None
    raw_foreground_ratio: float | None = None
    bridged_foreground_ratio: float | None = None
    morphology_foreground_area_px: int | None = None
    morphology_foreground_ratio: float | None = None
    filled_envelope_area_px: int | None = None
    filled_envelope_ratio: float | None = None
    point_a_local: Point2D | None = None
    point_b_local: Point2D | None = None
    measurement_line_y: float | None = None
    local_y_delta_px: float | None = None
    parallel_error_px: float | None = None
    chord_length_px: float | None = None
    pattern_model: str | None = None
    detected_pattern: str | None = None
    object_interval_count: int | None = None
    interval_count: int | None = None
    selected_intervals: list[ObjectInterval] | None = None
    raw_intervals: list[ObjectInterval] | None = None
    bridged_intervals: list[ObjectInterval] | None = None
    selected_valid_intervals: list[ObjectInterval] | None = None
    rejected_intervals: list[ObjectInterval] | None = None
    rejected_interval_reasons: list[str] | None = None
    interval_gaps: list[float] | None = None
    bundle_cluster_count: int | None = None
    bundle_clusters: list[BundleClusterDiagnostics] | None = None
    selected_bundle_cluster_id: int | None = None
    selected_bundle_interval_count: int | None = None
    selected_bundle_outer_span_px: float | None = None
    selected_bundle_support_ratio: float | None = None
    selected_bundle_max_internal_gap_px: float | None = None
    max_bundle_internal_gap_px: float | None = None
    max_bundle_internal_gap_ratio: float | None = None
    rejected_remote_intervals: list[ObjectInterval] | None = None
    rejected_remote_interval_reasons: list[str] | None = None
    remote_interval_rejection_count: int | None = None
    leftmost_valid_interval: ObjectInterval | None = None
    rightmost_valid_interval: ObjectInterval | None = None
    point_a_source_interval: ObjectInterval | None = None
    point_b_source_interval: ObjectInterval | None = None
    formal_point_a_source_interval: ObjectInterval | None = None
    formal_point_b_source_interval: ObjectInterval | None = None
    broad_blob_rejection_count: int | None = None
    broad_blob_area_ratio: float | None = None
    wire_components: list[WireComponentDiagnostics] | None = None
    accepted_components: list[WireComponentDiagnostics] | None = None
    rejected_components: list[WireComponentDiagnostics] | None = None
    local_contrast_score: float | None = None
    wire_likeness_score: float | None = None
    component_area_px: int | None = None
    component_bbox: ComponentBBox | None = None
    component_aspect_ratio: float | None = None
    component_orientation: float | None = None
    component_orientation_deg: float | None = None
    orientation_deviation_deg: float | None = None
    neighbor_line_support: int | None = None
    point_a_on_foreground_boundary: bool | None = None
    point_b_on_foreground_boundary: bool | None = None
    point_a_source_layer: str | None = None
    point_b_source_layer: str | None = None
    internal_gap_count: int | None = None
    max_internal_gap_px: float | None = None
    mesh_outer_span_px: float | None = None
    bundle_outer_span_px: float | None = None
    formal_ab_span_px: float | None = None
    selected_line_rank: int | None = None
    top_candidate_lines: list[CandidateLineDiagnostics] | None = None
    candidate_count: int | None = None
    ambiguous_candidate_count: int | None = None
    selected_line_span_px: float | None = None
    second_best_span_px: float | None = None
    span_margin_to_second_best_px: float | None = None
    selected_line_support_ratio: float | None = None
    selected_line_max_internal_gap_px: float | None = None
    selected_line_interval_count: int | None = None
    virtual_envelope_span_px: float | None = None
    candidate_line_is_debug_only: bool | None = None
    selected_line_reason: str | None = None
    measurement_mode: str | None = None
    previous_measurement_line_y: float | None = None
    line_y_delta_from_previous: float | None = None
    measurement_line_y_delta_from_previous: float | None = None
    distance_jump_from_previous: float | None = None
    abs_distance_jump_from_previous: float | None = None
    point_a_jump_from_previous: float | None = None
    point_b_jump_from_previous: float | None = None
    is_top_jump_candidate: bool | None = None
    jump_warning: str | None = None
    segmentation_ms: float | None = None
    connected_components_ms: float | None = None
    wire_filtering_ms: float | None = None
    line_scan_ms: float | None = None
    candidate_scoring_ms: float | None = None
    fill_holes_ms: float | None = None
    chord_scan_ms: float | None = None
    diagnostics_ms: float | None = None
    detector_total_ms: float | None = None
    foreground_area_px: int | None = None
    foreground_area_ratio_in_roi: float | None = None
    selected_component_area_px: int | None = None
    selected_component_bbox: ComponentBBox | None = None
    candidate_component_count: int | None = None
    min_local_projection: float | None = None
    max_local_projection: float | None = None
    roi_half_width: float | None = None
    distance_to_left_roi_boundary_px: float | None = None
    distance_to_right_roi_boundary_px: float | None = None
    left_margin_px: float | None = None
    right_margin_px: float | None = None
    top_margin_px: float | None = None
    bottom_margin_px: float | None = None
    boundary_margin_px: float | None = None
    rejected_contact_side: str | None = None
    rejected_candidate_point_a: Point2D | None = None
    rejected_candidate_point_b: Point2D | None = None
    fill_internal_holes_used: bool | None = None
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
            if self.point_a is not None or self.point_b is not None:
                raise ValueError("invalid detection results must not include formal points")

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
    segmentation: SegmentationParams
    detector: DetectorParams
    detector_version: str = "v1"
    acquisition_frame_size: AcquisitionFrameSize
    coordinate_space: CoordinateSpace = CoordinateSpace.ACQUISITION
    created_at_ms: int
    auto_tuned: bool = False
    auto_tune_score: float | None = None

    @field_validator("coordinate_space")
    @classmethod
    def require_acquisition_coordinates(cls, value: CoordinateSpace) -> CoordinateSpace:
        if value is not CoordinateSpace.ACQUISITION:
            raise ValueError("measurement definitions must be in acquisition coordinates")
        return value

    @model_validator(mode="after")
    def validate_detector_matches_target_family(self) -> MeasurementDefinition:
        expected_detector = {
            TargetFamily.BALLOON_ENVELOPE: DetectorKind.BALLOON_ENVELOPE_DETECTOR,
            TargetFamily.WIRE_STRIP: DetectorKind.WIRE_STRIP_DETECTOR,
        }[self.target_family]
        if self.detector.detector_kind is not expected_detector:
            raise ValueError("measurement detector params must match target_family")
        return self


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
