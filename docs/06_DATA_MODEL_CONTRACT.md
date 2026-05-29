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
    min_quality: float = 0.65
    max_point_jump_px: float | None = 25.0
    reject_contact_on_roi_boundary: bool = True
    boundary_margin_px: float = 4.0
    ignore_internal_texture: bool = True
    fill_internal_holes: bool = True
    bridge_mesh_gaps: bool = True

class WireStripDetectorParams(BaseModel):
    detector_kind: Literal[DetectorKind.WIRE_STRIP_DETECTOR] = DetectorKind.WIRE_STRIP_DETECTOR
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
    morphology_foreground_area_px: int | None = None
    morphology_foreground_ratio: float | None = None
    filled_envelope_area_px: int | None = None
    filled_envelope_ratio: float | None = None
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
    contact_source_used: str | None = None
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
