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

## A/B point definition

A/B points are contour contact points selected inside the current rotated ROI.

Given:

- a current frame
- a rotated ROI
- one of the two target families
- a measurement direction from the ROI angle

The selected target-specific detector extracts the valid external contour of the target inside the ROI. It then finds the two opposite support sides of that contour along the ROI measurement direction.

- Point A is the contour contact point on the smaller projection side.
- Point B is the contour contact point on the larger projection side.

A/B points must lie on valid target contour points.

A/B points must not be:

- ROI box corners
- axis-aligned bounding-box corners
- display-coordinate points
- pure mathematical projection points without contour support
- internal texture points
- mesh-hole points
- skeleton endpoints
- manually drawn points

## Measurement direction rule

Let `u` be the ROI measurement direction derived from `roi.angle_deg`.

For each valid contour point `p`, compute projection:

```text
s = dot(p, u)
```

The smaller-projection and larger-projection support sides define the two candidate contact regions.

Each target-specific detector chooses actual contour contact points near those two support sides and returns them as A/B.

The selected A/B points should be stable over time. If several candidate contacts are equally plausible, return `caliper_contact_ambiguous` unless temporal tracking can resolve the choice safely.

## ROI requirement

The ROI does not need to contain the physical endpoints of a wire-like sample.

The ROI must contain enough visible object contour to identify the two opposing contour sides in the measurement direction.

Invalid cases include:

- only one side of the contour is visible
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
A/B are ROI-direction contour contact points on the external envelope contour.
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
A/B are ROI-direction contour contact points on the visible strip contour inside the ROI.
```

Important:

- Do not search for whole-wire physical endpoints.
- Do not skeletonize for endpoint detection in the initial version.
- Do not return `wire_endpoint_missing`; that status is not part of this project.
- ROI may contain only a section of the wire/strip if both opposing contour sides are visible.

Common failure reasons:

- `target_not_found`
- `low_contrast`
- `multiple_targets`
- `opposing_contour_edges_missing`
- `caliper_contact_ambiguous`
- `caliper_contact_on_roi_boundary`
- `points_not_on_contour`
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
- projection values for A/B
- ROI-local A/B coordinates
- failure reason details

Diagnostic images can be stored later, but the API contract should not require them for MVP.
