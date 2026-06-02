# 20 — Debug Inspect And Point Probe

## Purpose

Setup detection, Live Offline Run, and Offline Validation must explain the same
formal detection path. This document defines how operators and developers inspect
small foreground specks without changing formal A/B selection.

Point probe and crop inspect are diagnostics only. They never compute, replace,
or carry forward formal A/B points.

## Frame Identity

Setup freeze, setup detection, Live Offline Run frames, inspect responses, debug
overlays, and Offline Validation samples expose a sanitized frame identity:

- `frame_id` or `frame_index`
- `frame_name` as a basename or safe label
- `source_type`
- acquisition frame width and height
- recipe summary
- `debug_level`

API responses, diagnostics, UI errors, and overlays must not return machine-local
absolute paths. The frame identity lets the user confirm that raw preview, debug
overlay, crop inspect, setup detection, and live run are describing the same
frame and recipe.

## View Types

Setup raw preview:

- shows the frozen grayscale acquisition frame through the normal preview path;
- may be downsampled to fit the browser;
- may hide 1 to 3 px specks after browser scaling.

Raw only:

- shows only the grayscale frame image;
- hides formal A/B, ROI, intervals, masks, and debug candidates;
- is for visually checking image content, not detector state.

Debug overlay:

- is an overview PNG with foreground and detection layers drawn on top;
- may be downsampled, so very small specks can become invisible;
- is useful for detector-stage interpretation but is not the source of truth for
  a single pixel or tiny component.

ROI crop inspect:

- uses the original acquisition frame crop around the ROI;
- supports 1x, 2x, and 4x nearest-neighbor zoom;
- preserves 1 to 3 px specks much better than full-frame overview images;
- is generated in memory and not committed as an artifact.

## Point Probe

Point probe queries one acquisition-coordinate point against the same wire-strip
debug evidence used by formal detection:

```text
POST /api/setup/probe-point
POST /api/offline-run/{session_id}/probe-point
```

The frontend may convert display coordinates to acquisition coordinates before
calling the API, but it must not calculate formal A/B.

The response reports:

- pixel value;
- whether the point is inside the ROI;
- whether it is in `raw_foreground`, `morphology_foreground`, or `wire_foreground`;
- component id and accepted/rejected state;
- component or interval reject reason when present;
- selected valid interval membership;
- rejected interval and rejected remote interval membership;
- whether the point belongs to the formal A/B source interval.

If a point is visible in raw preview but not in any foreground layer, masks and
components should be false/null. If it enters foreground but is remote from the
selected bundle cluster, it should appear as a rejected remote interval and
`would_be_ab_source` must be false.

## Same Detector Path

Setup detection, Live Offline Run, and Offline Validation must use the same
`WireStripDetector` formal `wire_bundle_envelope` logic for `wire_strip`.

`debug_level` controls diagnostic detail and overlay richness only. It must not
change:

- status;
- formal A/B coordinates;
- `distance_px`;
- selected bundle cluster;
- remote interval rejection.

For the same frame, ROI, segmentation params, detector params, measurement mode,
and threshold, setup detection, live offline basic/full detection, and offline
validation sample detection must return the same formal result.

## Remote Speck Interpretation

For `wire_bundle_envelope`, intervals on the selected measurement line are split
into bundle clusters by internal gap thresholds. A/B may only come from the
selected bundle cluster.

A far-right isolated speck can enter raw foreground and even pass component-level
wire filtering, but if its gap from the selected bundle cluster exceeds
`max_bundle_internal_gap_px` or `max_bundle_internal_gap_ratio`, it becomes a
rejected remote interval. Rejected remote intervals must not extend B.

Diagnostics that explain this include:

- `selected_valid_intervals`
- `rejected_intervals`
- `rejected_remote_intervals`
- `remote_interval_rejection_count`
- `selected_bundle_cluster_id`
- `selected_bundle_max_internal_gap_px`
- `selected_bundle_support_ratio`
- `formal_point_a_source_interval`
- `formal_point_b_source_interval`

## Operator Workflow

1. Freeze or seek to the frame of interest.
2. Check frame identity on the raw preview and debug overlay.
3. Enable Raw only if overlays obscure the speck.
4. Use ROI crop zoom at 2x or 4x to confirm that the speck exists in the raw image.
5. Enable Probe point and click the speck.
6. Read `pixel_value`, foreground flags, component state, interval state, reject reason,
   and `would_be_ab_source`.

If the point probe says `would_be_ab_source=false`, the speck cannot be the formal
A or B source even if it is visually present in the raw image.
