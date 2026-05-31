# 19. Wire Bundle Auto Tune

This document is the operator-facing contract for setup-time Wire Auto Tune. It
does not change the formal A/B contract from `docs/02_DETECTION_CONTRACT.md`.

## Measurement Mode

`wire_strip` currently means `wire_bundle_envelope`.

The formal pattern is:

```text
blank - wire_bundle_envelope - blank
```

On one ROI-local measurement line, the visible bundle may contain multiple
foreground intervals:

```text
blank | wire_1 | gap | wire_2 | gap | wire_3 | blank
```

The gaps are internal bundle spaces. They are not an inner-gap measurement
target. A is the left outer boundary of the leftmost valid wire interval. B is
the right outer boundary of the rightmost valid wire interval. A/B must be real
foreground-boundary points and must not be gap, background, ROI boundary,
virtual-envelope, or rejected/debug points.

The project does not implement `two_strip_outer_to_outer`, physical endpoint
detection, or inner-gap measurement.

## Setup Auto Tune

Manual fixed thresholds are useful for diagnosis but should not be the long-term
operator workflow. During setup, Wire Auto Tune sweeps fixed threshold candidates
and runs `WireStripDetector` with the current ROI and detector parameters.

Default candidates are based on fixed values plus ROI histogram candidates. The
fixed baseline keeps behavior reviewable; histogram candidates only add local
coverage.

Each threshold candidate records:

- threshold value, status, valid flag, and failure reason;
- formal A/B span and selected valid intervals;
- rejected interval count and broad-blob rejection evidence;
- local contrast, wire-likeness, neighbor-line support, and ROI margin;
- A/B foreground-boundary flags;
- score and stable-platform membership.

The recommended threshold is chosen from the best stable platform when one is
available. If no stable platform exists, the best valid candidate may be
reported with a lower-confidence reason. If there is no credible candidate,
setup fails safely and the user should adjust ROI, lighting, or background.

## Recipe Locking

Confirm Setup persists the selected segmentation and full
`WireStripDetectorParams` snapshot. This includes interval width/count gates,
local-contrast minimum, broad-blob/component-area limits, bundle internal-gap
limits, neighbor-line support, and diagnostic scoring toggles.

The effective remote-interval split threshold is:

```text
min(max_bundle_internal_gap_px, roi.width * max_bundle_internal_gap_ratio)
```

The default is capped at 60 px so a 173 px far-side gap in the 20260529 dev_lab
captures is treated as a remote separation, while normal bundle spacing below
that cap remains eligible.

Run, Live Offline Run, and Offline Validation apply the confirmed recipe
verbatim. They do not auto-tune per frame, do not use the previous
`measurement_line_y` to choose formal A/B, and do not fall back to the previous
A/B or distance.

## Diagnostics

Diagnostics must be enough to explain why B did or did not move to a side
component:

- `selected_valid_intervals`, `leftmost_valid_interval`, and
  `rightmost_valid_interval`;
- `rejected_intervals` and `rejected_interval_reasons`;
- `interval_gaps`, `bundle_clusters`, `selected_bundle_cluster_id`, and
  `selected_bundle_outer_span_px`;
- `rejected_remote_intervals`, `rejected_remote_interval_reasons`, and
  `remote_interval_rejection_count`;
- `max_bundle_internal_gap_px` and `max_bundle_internal_gap_ratio`;
- `local_contrast_score`, `wire_likeness_score`, `neighbor_line_support`;
- `broad_blob_rejection_count` and `broad_blob_area_ratio`;
- `component_area_px`, `component_bbox`, `component_aspect_ratio`, and
  `component_orientation_deg`;
- `formal_ab_span_px`, `bundle_outer_span_px`, `internal_gap_count`, and
  `max_internal_gap_px`;
- `point_a_on_foreground_boundary` and `point_b_on_foreground_boundary`.

Orientation and aspect ratio are diagnostics and weak score evidence in this
stage. Orientation is not a hard rejection gate because real wire bundles can
curve, fan out, or split.
