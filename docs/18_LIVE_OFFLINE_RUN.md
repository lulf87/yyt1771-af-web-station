# 18 — Live Offline Run

## Purpose

Live Offline Run is a simulated-camera run mode for real local offline frames.

It lets the browser step through a `.npy` or PGM frame folder in natural frame order, show a downsampled preview, and run the confirmed detector on every frame. This is for observing A/B stability in the GUI before any Hik MVS adapter work.

This phase does not replace batch Run, offline validation, or Playback.

## Relationship To Existing Modes

Batch Run:

- uses `POST /api/runs/start`,
- samples a finite count of frames,
- stores samples under `runs/`,
- feeds analysis and export,
- returns after the batch finishes.

Offline Playback:

- uses `/api/offline-playback/*`,
- can replay existing `evaluation_samples.jsonl`,
- is useful for reviewing validation artifacts.

Live Offline Run:

- uses `/api/offline-run/*`,
- keeps a backend session open,
- lazy-loads one frame at a time,
- detects A/B on demand for each frame,
- updates the Run page as a simulated live camera view.

## Source Folder

Set the local offline frame folder:

```bash
export YYT1771_AF_OFFLINE_DIR="/absolute/path/to/local/frames"
```

Real camera capture folders follow this layout:

```text
capture_id/
  frames/frame_000001.npy
  frames/frame_000002.npy
  ...
  temperature.csv
  manifest.json
```

When `frames_dir` points at `capture_id/frames`, Live Offline Run automatically
loads the sibling `temperature.csv` (one row per captured frame, keyed by
1-based `frame_index`). Temperature values are replayed per frame during Live
Offline Run; API responses expose `celsius` and `source` but never absolute
paths to the CSV file.

When the Run page opens a Live Offline Run without an explicit `frames_dir`, the backend uses `YYT1771_AF_OFFLINE_DIR`.

## Locked Measurement Definition

Live Offline Run requires a Confirm Setup result.

The backend copies the confirmed `MeasurementDefinition` into the session. The locked snapshot includes:

- target family,
- ROI in acquisition coordinates,
- segmentation parameters,
- detector parameters,
- detector version,
- envelope mode and contact source for `BalloonEnvelopeDetector`,
- measurement model and mode where applicable.

During playback, Run does not auto tune, does not restore recipe defaults, does not change ROI, and does not carry A/B forward from prior frames.

## Per-Frame Detection

For each `next`, `previous`, or `seek` request:

1. The backend lazy-loads the requested frame.
2. `.npy` loading uses `np.load(..., allow_pickle=False)`.
3. The detector runs with the locked ROI and recipe.
4. Formal A/B points are returned only when the result is valid.
5. Invalid frames return `point_a = null`, `point_b = null`, and `distance_px = null`.
6. Rejected/debug candidates may appear only in diagnostics.

The frontend only maps acquisition coordinates into the SVG overlay. It does not compute formal A/B, formal distance, segmentation, intervals, or contact points.

For `wire_strip` with `wire_bundle_envelope`, a valid basic response carries the
formal source summary needed to explain A/B without full interval arrays:

- `point_a_source_interval`
- `point_b_source_interval`
- `selected_bundle_cluster_id`
- `selected_bundle_support_ratio`
- `selected_bundle_max_internal_gap_px`
- `remote_interval_rejection_count`

Full debug responses additionally carry `selected_valid_intervals`,
`leftmost_valid_interval`, `rightmost_valid_interval`,
`rejected_remote_intervals`, and rejected interval reasons.

The detector invariant is that A comes from the left boundary of the leftmost
selected valid interval and B comes from the right boundary of the rightmost
selected valid interval. A/B must not come from rejected remote intervals. If
the invariant fails, the frame is invalid and formal A/B/distance are null.

## API

Open:

```text
POST /api/offline-run/open
```

Request:

```json
{
  "measurement_definition_id": "md_xxx",
  "frames_dir": null,
  "fps": 10,
  "loop": true,
  "dataset_label": null,
  "start_frame_index": 0,
  "max_preview_width": 1200
}
```

Session operations:

```text
GET  /api/offline-run/{session_id}/status
POST /api/offline-run/{session_id}/next
POST /api/offline-run/{session_id}/inspect
POST /api/offline-run/{session_id}/previous
POST /api/offline-run/{session_id}/seek
POST /api/offline-run/{session_id}/close
GET  /api/offline-run/{session_id}/trace
GET  /api/offline-run/{session_id}/frame/{frame_index}/preview.png?max_width=1200
```

The `preview_url` always includes the session id so multiple sessions cannot cross-read different datasets.

`inspect` re-runs the current frame with `debug_level = full` and does not
advance `current_frame_index` or `next_frame_index`.

## Error Model

Live Offline Run separates detector results from transport/API failures.

- Detection invalid means `/next`, `previous`, or `seek` returned HTTP 200 with
  `detection.valid = false`. The UI shows the detection status, draws no formal
  A/B points, and playback may continue.
- API error means a session, frame read, detector, or preview endpoint request
  failed. The backend returns structured JSON with `state = "error"`,
  `error_code`, sanitized `message`, `session_id`, and, when available,
  `frame_index` plus the frame-name basename.
- Preview error means the frame response succeeded but the browser failed to load
  the `preview.png` image. The UI reports this separately from detection invalid.
- End of stream is represented by `end_of_stream = true` when `loop = false`.
  When `loop = true`, `next` wraps to frame 0.

Supported structured error codes include:

```text
session_not_found
frame_index_out_of_range
frame_read_failed
unsupported_frame_format
detection_failed
preview_encode_failed
measurement_definition_missing
```

Error responses and trace payloads must not expose `frames_dir`, `/Users/...`,
`C:\Users\...`, or any other local absolute path.

## Trace Buffer

Each open session keeps a bounded in-memory trace buffer for the most recent
frames. `GET /api/offline-run/{session_id}/trace` returns sanitized entries with:

- frame index and frame-name basename
- detection status, validity, distance, point A/B
- ROI-local `measurement_line_y`
- `formal_ab_span_px`
- formal `point_a_source_interval` and `point_b_source_interval`
- selected wire interval and bundle-cluster summary
- `selected_bundle_support_ratio`
- `selected_bundle_max_internal_gap_px`
- `remote_interval_rejection_count`
- whether A/B are on foreground boundaries
- jump diagnostics from the previous valid frame
- per-frame timings
- `error_code` for API/preview/read errors

The trace is for diagnosis only. It is not persisted as run output and it does not
change formal A/B selection.

## Performance Timings

Runtime payloads expose coarse request timings and detector-stage timings:

- `load_ms`
- `frame_load_ms`
- `detect_ms`
- `api_total_ms`
- `preview_encode_ms`
- `target_fps`
- `frame_budget_ms`
- `segmentation_ms`
- `connected_components_ms`
- `wire_filtering_ms`
- `line_scan_ms`
- `candidate_scoring_ms`
- `fill_holes_ms`
- `chord_scan_ms`
- `diagnostics_ms`
- `detector_total_ms`

`api_total_ms` covers the `/next` request path and does not include the browser's
subsequent image fetch. `preview_encode_ms` comes from the `preview.png` endpoint.
The Run page compares timings to `frame_budget_ms = 1000 / target_fps`:

- `detect_ms > 0.8 * frame_budget_ms` shows detector-limited,
- `preview_encode_ms > 0.3 * frame_budget_ms` shows preview-limited,
- `api_total_ms > frame_budget_ms` without detector saturation shows
  network/api-limited.

If the detector is slower than the budget, measured FPS will be lower than target
FPS. The warning does not change detector output or the formal A/B contract.

## Debug Level Policy

Playing uses `debug_level = basic`. Basic mode returns formal detection,
essential source diagnostics, jump diagnostics, and timings. It skips full
raw/bridged/selected/rejected interval arrays and does not generate debug overlay PNGs.
The essential wire source diagnostics are enough to explain formal A/B origin
without returning full overlay metadata on every playback frame.

Pause, step, seek, and explicit debug inspection use `debug_level = full`.
Full debug returns selected intervals, rejected remote intervals, source
intervals, and overlay metadata. Full debug is for inspection and should not be
used as the default playback path.

## Drift Diagnostics

For `wire_strip`, the formal selected line remains the current frame's valid line
with the largest `formal_ab_span_px`. Previous-frame data is diagnostics only.

Live Offline Run may report:

- `previous_measurement_line_y`
- `line_y_delta_from_previous`
- `measurement_line_y_delta_from_previous`
- `distance_jump_from_previous`
- `abs_distance_jump_from_previous`
- `point_a_jump_from_previous`
- `point_b_jump_from_previous`
- `is_top_jump_candidate`
- `jump_warning`

These fields can explain distance or line-y drift, but they must not influence
the current frame's formal A/B selection.

## Run Page Workflow

1. Start backend and frontend.
2. In Setup, open the offline source, freeze a frame, draw ROI, tune recipe, and confirm setup.
3. Go to Run.
4. Select `Live Offline Run`.
5. Click `Open Live Source`.
6. Use `Play`, `Pause`, `Step Prev`, `Step Next`, and `Seek`.
7. Use `Inspect current frame` while paused to request full diagnostics without
   advancing playback.
8. Adjust FPS and Loop before opening the session.

The frame preview is downsampled for the browser. Formal ROI and A/B coordinates remain in the original acquisition frame size.

## Overlay Rules

When `valid = true`:

- draw the confirmed ROI,
- draw FORMAL A/B points,
- draw only the formal A-to-B segment,
- do not show rejected/debug candidates as formal points.
- when diagnostics overlay is enabled, draw selected valid intervals, formal
  source intervals, and full-debug rejected remote intervals as diagnostic
  overlays only.

When `valid = false`:

- draw the confirmed ROI,
- do not draw formal A/B,
- optionally draw rejected/debug candidates with rejected/debug styling,
- keep `distance_px` as `N/A`.

## Hik MVS Boundary

Live Offline Run is still offline-only. It does not implement, import, or configure Hik MVS. Real camera adapter work remains deferred.
