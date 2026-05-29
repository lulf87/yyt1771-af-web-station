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

The selected A/B points should be stable over time. If several measurement lines or interval patterns are equally plausible, return `caliper_contact_ambiguous` unless temporal tracking can resolve the choice safely.

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
A wire/strip target is a visible thin or elongated object inside the ROI. The detector measures the visible contour within the ROI, not the physical endpoints of the full object.
```

A/B rule:

```text
The formal pattern is blank - object - blank - object - blank.

The default measurement mode is outer-to-outer.

A is the left outer contour/scanline boundary of the first object interval on the selected ROI-local measurement line.
B is the right outer contour/scanline boundary of the second object interval on the same ROI-local measurement line.
```

Important:

- Do not search for whole-wire physical endpoints.
- Do not skeletonize for endpoint detection in the initial version.
- Do not return `wire_endpoint_missing`; that status is not part of this project.
- Do not measure the inner gap unless a future `inner_to_inner` mode is explicitly defined.
- A line with only one object interval is invalid for `wire_strip`.

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
- temporal jump from previous frame if tracking context exists

Quality is not a substitute for status. A result can have low quality and still expose a specific failure reason.

## Temporal stability

Live detection should not treat each frame as fully independent if previous valid points exist.

Allowed stabilizers:

- previous A/B prior
- max jump threshold
- candidate scoring using temporal continuity
- smoothing for display only

Raw stored `distance_px` must remain based on actual frame detection, not display-only smoothing.

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
