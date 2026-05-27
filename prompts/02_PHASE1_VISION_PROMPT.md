# Prompt 02 — Phase 1 Vision Detectors

Implement the first tested versions of the two target-specific detectors:

```text
BalloonEnvelopeDetector
WireStripDetector
```

Do not implement a third public detector in the initial version.

Read:

- `docs/02_DETECTION_CONTRACT.md`
- `docs/06_DATA_MODEL_CONTRACT.md`
- `docs/09_TEST_PLAN.md`

## Required behavior

Implement pure vision paths that:

1. Accept a grayscale frame, rotated ROI, target family, and target-specific recipe params.
2. Dispatch to exactly one of the two detectors based on `target_family`.
3. Crop/transform the ROI as needed.
4. Segment the target.
5. Extract the valid contour for the selected target family.
6. Select A/B contour contact points on the smaller/larger projection sides along ROI angle.
7. Return `DetectionResult` with `distance_px` as Euclidean pixel distance.
8. Return explicit failure statuses for invalid cases.

## Required detector behavior

### `BalloonEnvelopeDetector`

- Treat the target as a whole external envelope.
- Ignore internal mesh/noise where possible.
- Prefer the outer envelope contour.
- Reject internal texture as A/B.

### `WireStripDetector`

- Treat the target as visible strip/wire-like contour inside the ROI.
- Do not search for physical endpoints.
- Do not skeletonize for endpoint detection.
- Do not return `wire_endpoint_missing`.

## Required tests

Add synthetic tests for:

- solid ellipse / balloon target
- ellipse with internal mesh/noise
- straight strip target
- rotated strip target
- object touching ROI boundary
- only one opposing contour side visible

## Important

- Public detector classes should be target-specific only.
- Shared projection or ROI helper functions are allowed, but not a third public detector.
- A/B must be contour contact points, not ROI corners or display points.
- All returned A/B points must be in acquisition coordinates.
