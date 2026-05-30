# 06 — Data Model Contract

This file defines the canonical data models. Codex should implement these as Pydantic models or equivalent typed Python models.

## Enums

```python
from enum import StrEnum

class CoordinateSpace(StrEnum):
    SENSOR_NATIVE = "sensor_native"
    ACQUISITION = "acquisition"
    ROI_LOCAL = "roi_local"
    DISPLAY = "display"

class TargetFamily(StrEnum):
    BALLOON_ENVELOPE = "balloon_envelope"
    WIRE_STRIP = "wire_strip"

class DetectorKind(StrEnum):
    BALLOON_ENVELOPE_DETECTOR = "balloon_envelope_detector"
    WIRE_STRIP_DETECTOR = "wire_strip_detector"

class DetectionStatus(StrEnum):
    OK = "ok"
    NO_FRESH_FRAME = "no_fresh_frame"
    ROI_INVALID_GEOMETRY = "roi_invalid_geometry"
    ROI_OUTSIDE_FRAME = "roi_outside_frame"
    TARGET_NOT_FOUND = "target_not_found"
    LOW_CONTRAST = "low_contrast"
    SEGMENTATION_FAILED = "segmentation_failed"
    MULTIPLE_TARGETS = "multiple_targets"
    TARGET_TOUCHES_ROI_BOUNDARY = "target_touches_roi_boundary"
    OPPOSING_CONTOUR_EDGES_MISSING = "opposing_contour_edges_missing"
    CALIPER_CONTACT_AMBIGUOUS = "caliper_contact_ambiguous"
    CALIPER_CONTACT_ON_ROI_BOUNDARY = "caliper_contact_on_roi_boundary"
    CONTOUR_FRAGMENTED = "contour_fragmented"
    INTERNAL_TEXTURE_SELECTED = "internal_texture_selected"
    POINTS_NOT_ON_CONTOUR = "points_not_on_contour"
    PATTERN_NOT_FOUND = "pattern_not_found"
    OBJECT_INTERVAL_COUNT_MISMATCH = "object_interval_count_mismatch"
    QUALITY_BELOW_THRESHOLD = "quality_below_threshold"
    JUMP_EXCEEDS_LIMIT = "jump_exceeds_limit"
    COORDINATE_MAPPING_ERROR = "coordinate_mapping_error"
    STALE_FRAME_GEOMETRY_MISMATCH = "stale_frame_geometry_mismatch"
    UNSUPPORTED_TARGET_FAMILY = "unsupported_target_family"
```

Do not add `wire_endpoint_missing` in the initial version.

## Geometry models

```python
class Point2D(BaseModel):
    x: float
    y: float
    coordinate_space: CoordinateSpace = CoordinateSpace.ACQUISITION

class RotatedRoi(BaseModel):
    center_x: float
    center_y: float
    width: float
    height: float
    angle_deg: float
    coordinate_space: CoordinateSpace = CoordinateSpace.ACQUISITION

class FrameRef(BaseModel):
    frame_id: int
    timestamp_ms: int
    width: int
    height: int
    coordinate_space: CoordinateSpace = CoordinateSpace.ACQUISITION
```

## Runtime frame model

The frame data itself should not be serialized through JSON except as a preview image.

```python
class Frame:
    frame_id: int
    timestamp_ms: int
    width: int
    height: int
    coordinate_space: CoordinateSpace
    image: np.ndarray
```

## Recipe models

The initial project has exactly two target-specific detector parameter models. Do not implement one generic public detector model.

```python
class SegmentationParams(BaseModel):
    polarity: Literal["dark_on_light", "light_on_dark", "auto"] = "auto"
    threshold_mode: Literal["otsu", "adaptive", "fixed"] = "otsu"
    threshold_value: int | None = None
    blur_kernel: int = 3
    close_kernel: int = 5
    open_kernel: int = 3
    min_component_area_px: int = 50

class BalloonEnvelopeDetectorParams(BaseModel):
    detector_kind: Literal[DetectorKind.BALLOON_ENVELOPE_DETECTOR] = DetectorKind.BALLOON_ENVELOPE_DETECTOR
    envelope_mode: Literal["solid_balloon", "open_mesh"] = "solid_balloon"
    contact_source: Literal["raw_foreground", "bridged_foreground", "filled_envelope"] = "filled_envelope"
    measurement_model: Literal["blank_object_blank"] = "blank_object_blank"
    min_quality: float = 0.65
    max_point_jump_px: float | None = 25.0
    reject_contact_on_roi_boundary: bool = True
    boundary_margin_px: float = 4.0
    ignore_internal_texture: bool = True
    fill_internal_holes: bool = True
    bridge_mesh_gaps: bool = True

class WireStripDetectorParams(BaseModel):
    detector_kind: Literal[DetectorKind.WIRE_STRIP_DETECTOR] = DetectorKind.WIRE_STRIP_DETECTOR
    measurement_model: Literal["blank_wire_bundle_envelope_blank"] = "blank_wire_bundle_envelope_blank"
    measurement_mode: Literal["wire_bundle_envelope"] = "wire_bundle_envelope"
    min_quality: float = 0.60
    max_point_jump_px: float | None = 20.0
    reject_contact_on_roi_boundary: bool = True
    boundary_margin_px: float = 3.0
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
```

## Detection result

```python
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
    foreground_area_px: int | None = None
    foreground_area_ratio_in_roi: float | None = None
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
    selected_intervals: list[dict] | None = None
    raw_intervals: list[dict] | None = None
    bridged_intervals: list[dict] | None = None
    selected_valid_intervals: list[dict] | None = None
    rejected_intervals: list[dict] | None = None
    rejected_interval_reasons: list[str] | None = None
    leftmost_valid_interval: dict | None = None
    rightmost_valid_interval: dict | None = None
    formal_point_a_source_interval: dict | None = None
    formal_point_b_source_interval: dict | None = None
    broad_blob_rejection_count: int | None = None
    broad_blob_area_ratio: float | None = None
    wire_likeness_score: float | None = None
    component_aspect_ratio: float | None = None
    component_orientation: float | None = None
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
    virtual_envelope_span_px: float | None = None
    candidate_line_is_debug_only: bool | None = None
    selected_line_reason: str | None = None
    measurement_mode: str | None = None
    previous_measurement_line_y: float | None = None
    line_y_delta_from_previous: float | None = None
    distance_jump_from_previous: float | None = None
    point_a_jump_from_previous: float | None = None
    point_b_jump_from_previous: float | None = None
    selected_component_area_px: int | None = None
    selected_component_bbox: dict | None = None
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
    quality: float
    target_family: TargetFamily
    frame_ref: FrameRef | None = None
    diagnostics: DetectionDiagnostics
```

Rules:

- If `valid == true`, then `status == ok`, `point_a`, `point_b`, and `distance_px` must be present.
- If `valid == false`, then `distance_px` must be null.
- If `valid == false`, formal `point_a` and `point_b` must be null. Debug-only
  rejected candidates may appear under `diagnostics.rejected_candidate_point_a` and
  `diagnostics.rejected_candidate_point_b`; they are not measurement outputs.
- `quality` must always be present.
- `point_a` and `point_b`, when present, must be in `acquisition` coordinates.
- `diagnostics.detector` must be either `balloon_envelope_detector` or `wire_strip_detector`.

## Measurement definition

Confirmed setup must persist a complete recipe snapshot, not only a recipe name:

```python
class MeasurementDefinition(BaseModel):
    measurement_definition_id: str
    name: str
    target_family: TargetFamily
    roi: RotatedRoi
    recipe_name: str
    segmentation: SegmentationParams
    detector: BalloonEnvelopeDetectorParams | WireStripDetectorParams
    detector_version: str = "v1"
    acquisition_frame_size: AcquisitionFrameSize
    coordinate_space: CoordinateSpace = CoordinateSpace.ACQUISITION
    auto_tuned: bool = False
    created_at_ms: int
```

`auto_tuned` is `True` only when the confirmed `segmentation.threshold_value` came
from the setup-phase Wire Auto Tune sweep (see `docs/19`). It is metadata for
traceability; the run phase always applies the confirmed recipe verbatim.

Run-time detection must use this confirmed `segmentation` and `detector` snapshot. It must not silently reload default detector params from `recipe_name`.

The saved detector snapshot must include the measurement contract parameters:

- `BalloonEnvelopeDetectorParams.measurement_model = "blank_object_blank"`
- `WireStripDetectorParams.measurement_model = "blank_wire_bundle_envelope_blank"`
- `WireStripDetectorParams.measurement_mode = "wire_bundle_envelope"`
- detector version

Formal A/B points remain in acquisition coordinates. ROI-local A/B, `measurement_line_y`, `local_y_delta_px`, and `parallel_error_px` are diagnostics that verify the same-line chord contract.

## Run sample

```python
class RunSample(BaseModel):
    run_id: str
    sample_index: int
    timestamp_ms: int
    temperature_c: float | None = None
    detection: DetectionResult
```

## Run definition

```python
class RunDefinition(BaseModel):
    run_id: str
    recipe: MeasurementRecipe
    sample_hz: float
    created_at_ms: int
    profile_name: str
```

## Serialization

Use JSON for configuration and run metadata.

Use JSON Lines for streaming samples:

```text
samples.jsonl
```

Each line is a serialized `RunSample`.
