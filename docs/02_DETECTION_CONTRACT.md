# 02 — Detection Contract

This file defines the vision measurement behavior. It is the most important product contract in the project.

## Main measurement

The system measures:

```text
distance_px = sqrt((B.x - A.x)^2 + (B.y - A.y)^2)
```

The unit is pixel. The distance type is Euclidean.

Do not add millimeter conversion in the initial version.

## Coordinate rule

Formal ROI, A/B points, and `distance_px` are defined in `acquisition` coordinates.

Display coordinates are only for browser drawing.

## Public detector scope

The project has exactly two public detector implementations in the initial design:

```text
BalloonEnvelopeDetector
WireStripDetector
```

Do not create a third public detector in the initial version.

Both target-specific detectors may share small geometry helper functions for projection, ROI-local transforms, and contour-contact scoring. Shared helpers are allowed, but the product behavior, recipes, tests, and diagnostics must be expressed through the two target-specific detectors only.

## ROI and A/B point definition

The ROI is the main geometry window confirmed during setup and used during live run. It is a rotatable rectangle in `acquisition` coordinates, defined by `center_x`, `center_y`, `width`, `height`, and `angle_deg`.

`roi.angle_deg` defines the ROI local x-axis. This local x-axis is the formal measurement direction. The ROI local y-axis is perpendicular to the ROI local x-axis.

A ROI-local measurement line is a line with `y = constant` in the ROI local coordinate system. Its direction is strictly parallel to the ROI local x-axis.

Formal A/B must come from the same ROI-local measurement line:

- `A_local.y == B_local.y`.
- Discrete pixel implementations may allow only a very small tolerance, such as `<= 1 px`.
- The A/B line must be strictly parallel to the ROI local x-axis.
- Do not describe this as "roughly parallel", "mostly parallel", or "usually close".

A/B are formal measurement points in `acquisition` coordinates. They are not display-coordinate points.

A/B points must lie on valid target contour or scanline boundary points selected by the target-specific detector.

A/B points must not be:

- ROI box corners
- axis-aligned bounding-box corners
- display-coordinate points
- ROI frame-edge points created by cropping
- pure mathematical projection points without contour or scanline boundary support
- internal texture points
- mesh-hole points
- skeleton endpoints
- manually drawn points
- algorithm helper points
- rejected/debug candidates

Rejected/debug candidates may appear only in diagnostics. They must never be promoted to formal A/B.

## Measurement line rule

Each detector must choose A/B by evaluating ROI-local measurement lines, not by independently choosing minimum and maximum projection support points.

For each candidate measurement line:

- sample or intersect the detector-selected foreground/contour along one `y = constant` ROI-local line;
- identify object intervals on that line;
- validate the target-specific pattern;
- select A/B from the required interval boundaries;
- reject the frame if the line contact is caused by ROI cropping or the pattern is not trustworthy.

The selected A/B points should be stable over time. For `wire_strip`, the formal selected line is the current frame's valid line with the largest `formal_ab_span_px`; previous-frame line position must not affect that formal selection in this stage.

## ROI requirement

The ROI does not need to contain the physical endpoints of a wire-like sample.

The ROI must contain enough visible object contour along one or more ROI-local measurement lines to identify the required target pattern.

Invalid cases include:

- the required object interval pattern is not present
- the contact point is created by ROI cropping rather than the object boundary
- the target touches the ROI boundary in the measurement direction
- the foreground is fragmented so no valid external contour can be selected

## Detector: `BalloonEnvelopeDetector`

Target family:

```text
balloon_envelope
```

Definition:

```text
A balloon envelope target is treated as one whole external envelope. Internal mesh, holes, reflection, markings, and texture are not measurement targets.
```

A/B rule:

```text
The formal pattern is blank - object - blank.

A/B are the left and right real contour/scanline boundary contacts of the object/envelope on the same ROI-local measurement line.
```

For `envelope_mode = open_mesh`, a single ROI-local measurement line may contain multiple valid mesh foreground intervals:

```text
blank | interval_1 | gap | interval_2 | gap | interval_3 | blank
```

These intervals may be interpreted as one effective mesh envelope object, but the formal A/B points must still come from real foreground interval boundaries:

- A is the left outer boundary of the leftmost valid interval on the selected contact source.
- B is the right outer boundary of the rightmost valid interval on the selected contact source.
- Internal gaps are mesh voids; they may be inside the measured span but can never be A or B.
- `mesh_outer_span` is not a virtual envelope boundary, not a ROI-edge span, and not a filled-envelope background edge.
- For `open_mesh`, `filled_envelope` is a debug layer only unless a later contract explicitly allows it; the default formal contact source is `bridged_foreground`.

Expected preprocessing:

- bridge small mesh gaps
- close small holes
- fill internal holes where appropriate
- prefer outer contour over internal contours
- reject internal texture as measurement target

Common failure reasons:

- `target_not_found`
- `low_contrast`
- `multiple_targets`
- `contour_fragmented`
- `internal_texture_selected`
- `caliper_contact_on_roi_boundary`
- `points_not_on_contour`

Diagnostics must report detector identity as:

```text
balloon_envelope_detector:v1
```

## Detector: `WireStripDetector`

Target family:

```text
wire_strip
```

Definition:

```text
A wire/strip target is a visible wire bundle inside the ROI. The detector measures the bundle envelope width inside the ROI, not the physical endpoints of the full object.
```

A/B rule:

```text
The formal pattern is blank - wire_bundle_envelope - blank.

The only current formal measurement mode is wire_bundle_envelope.

On one ROI-local measurement line, the wire bundle may contain multiple valid wire foreground intervals:

blank | wire_1 | gap | wire_2 | gap | wire_3 | blank

These gaps are internal wire-bundle spaces, not multiple independent measurement objects.

Valid intervals on the same line are split into bundle clusters when an
internal gap exceeds the configured bundle-gap threshold. Formal A/B may only
come from the selected bundle cluster. Intervals split away from that cluster
are rejected as remote intervals and must not extend B, even if they are
high-contrast foreground.

A is the left outer boundary of the leftmost valid wire interval on the selected ROI-local measurement line.
B is the right outer boundary of the rightmost valid wire interval on the same ROI-local measurement line.
```

Important:

- Do not search for whole-wire physical endpoints.
- Do not skeletonize for endpoint detection in the initial version.
- Do not return `wire_endpoint_missing`; that status is not part of this project.
- Do not measure an inner gap in the current project.
- Do not implement or expose a two-strip outer-to-outer mode.
- A/B must be on real wire foreground interval boundaries.
- A/B must not be gap, background, ROI-boundary, virtual-envelope, or debug-candidate points.
- A line without enough valid wire interval support is invalid for `wire_strip`.
- Run detection must choose the current frame's valid candidate line with the largest `formal_ab_span_px`.
- If multiple valid candidate lines have spans within a very small configured
  tolerance, the detector may use deterministic tie-break diagnostics such as
  support ratio, internal gap, interval count, wire-likeness score, and ROI-center
  proximity. Previous-frame `measurement_line_y` is diagnostic only in this
  stage and must not override a clearly larger current-frame span.
- If near-equal candidates are low quality or otherwise unstable, the detector
  must return an explicit invalid status with null A/B and distance rather than
  promoting a debug candidate.

Wire foreground filtering (formal):

```text
Before line scanning, the general foreground mask is reduced to a trusted wire
foreground by component-level filtering: area bounds, slenderness / aspect ratio,
local contrast, neighbor-line support, internal-gap limits, and broad-blob
rejection. Background blobs (e.g. a screw hole or a gray non-target region) are
removed before A/B selection, so they cannot extend the formal bundle outer span.
Orientation and aspect ratio are recorded and scored for diagnostics in this
stage; orientation is not a hard rejection gate because real wire bundles can
curve, split, and fan out. Internal wire-bundle gaps are capped so disjoint
non-wire regions are not merged into one bundle.

The bundle-gap threshold is recorded separately from the selected cluster's
actual `max_internal_gap_px`. `max_bundle_internal_gap_px` is the effective
threshold used to split clusters.
```

Setup-only threshold tuning: fixed thresholds are fragile, so the setup phase may
run Wire Auto Tune (threshold sweep + scoring + stable-platform selection) and
persist the chosen fixed threshold into the confirmed recipe. The run phase never
auto-tunes; it applies the confirmed recipe verbatim. See `docs/19`.

Common failure reasons:

- `target_not_found`
- `low_contrast`
- `multiple_targets`
- `opposing_contour_edges_missing`
- `caliper_contact_ambiguous`
- `caliper_contact_on_roi_boundary`
- `points_not_on_contour`
- `pattern_not_found`
- `object_interval_count_mismatch`
- `jump_exceeds_limit`

Diagnostics must report detector identity as:

```text
wire_strip_detector:v1
```

## Failure states

Use explicit status strings. Initial enum:

```text
ok
no_fresh_frame
roi_invalid_geometry
roi_outside_frame
target_not_found
low_contrast
segmentation_failed
multiple_targets
target_touches_roi_boundary
opposing_contour_edges_missing
caliper_contact_ambiguous
caliper_contact_on_roi_boundary
contour_fragmented
internal_texture_selected
points_not_on_contour
quality_below_threshold
jump_exceeds_limit
coordinate_mapping_error
stale_frame_geometry_mismatch
unsupported_target_family
```

Do not add `wire_endpoint_missing` unless the product contract is later changed to endpoint-based wire detection.

## Quality score

Each detection returns a numeric quality score in `[0.0, 1.0]`.

The score should consider:

- segmentation confidence
- contour continuity
- target area plausibility
- contact-point boundary support
- distance from ROI boundary
- temporal jump from previous frame for diagnostics and validation only

Quality is not a substitute for status. A result can have low quality and still expose a specific failure reason.

## Temporal stability

For the current `wire_bundle_envelope` stage, previous-frame information is diagnostics only. It may be recorded as `previous_measurement_line_y`, `line_y_delta_from_previous`, `distance_jump_from_previous`, `point_a_jump_from_previous`, and `point_b_jump_from_previous`, but it must not change the current frame's formal A/B selection.

Future temporal continuity would require a separate design stage and, at most, a very weak tie-break when candidate `formal_ab_span_px` values differ by a tiny tolerance.

## Diagnostics

A detection result may include diagnostic data:

- detector identity: `balloon_envelope_detector:v1` or `wire_strip_detector:v1`
- selected contour area
- contour point count
- mask area
- number of candidate components
- ROI-local measurement line y
- ROI-local A/B coordinates
- local-y delta and parallel error
- chord length
- pattern model and detected pattern
- selected object intervals
- selected wire intervals and bundle outer span when `target_family = wire_strip`
- ROI-local A/B coordinates
- failure reason details

Diagnostic images can be stored later, but the API contract should not require them for MVP.

## Live Run Rule

During live run, the confirmed setup ROI and recipe are locked by default.

Each frame must re-detect A/B using:

- the same ROI,
- the same target family,
- the same public detector,
- the same detector mode,
- the same segmentation and detector recipe snapshot,
- the same measurement model and measurement mode.

The run stage must not freely switch threshold, contact source, envelope mode, measurement model, or measurement mode from frame to frame. If a future limited compensation feature is added, it must be explicitly designed and recorded.

If the current frame cannot be measured reliably, return an invalid status. Do not fabricate A/B points.
