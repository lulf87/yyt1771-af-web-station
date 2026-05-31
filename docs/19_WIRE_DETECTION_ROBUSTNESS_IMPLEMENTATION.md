# 19. Wire Detection Robustness & Auto-Tuning Implementation

This document records the concrete, shipped contract for making
`WireStripDetector` (`wire_bundle_envelope`) robust in offline/mock environments,
and for the setup-phase Wire Auto Tune. It complements the principles in
`docs/17` and the formal A/B rules in `docs/02`.

## Scope and invariants

- `WireStripDetector` supports only `measurement_mode = wire_bundle_envelope`.
- No physical-endpoint detection, no inner-gap measurement, no
  `two_strip_outer_to_outer`.
- Every frame's A/B must lie on real wire foreground interval boundaries, on one
  ROI-local measurement line, with A→B parallel to the ROI local x-axis.
- When no valid bundle is found, `point_a`, `point_b`, and `distance_px` are
  `null`.
- `previous_measurement_line_y` and previous-frame jumps are diagnostics only and
  must not influence the current frame's formal A/B.
- No OpenCV dependency, no Hik MVS adapter changes, no third public detector.
- No absolute paths in API responses, JSON artifacts, or diagnostics.

## Phase 1 — Diagnostics / Overlay baseline

Adds visibility without changing formal A/B. New `DetectionDiagnostics` fields
(see `docs/06`):

- `rejected_intervals`, `rejected_interval_reasons`
- `broad_blob_rejection_count`, `broad_blob_area_ratio`
- `wire_likeness_score`, `component_aspect_ratio`, `component_orientation`
- `neighbor_line_support`
- plus echoed recipe context: `threshold_mode`, `configured_polarity`,
  `close_kernel`, `open_kernel`, `min_component_area_px`.

The server overlay (`report/debug_overlay.py`) draws valid intervals, rejected
intervals (red dashed), and reports broad-blob / wire-likeness info in the
header. The frontend status panel surfaces the same fields.

## Phase 2 — Wire interval filtering

`vision/wire_filtering.py` reduces the general foreground mask to a trusted wire
foreground via component-level metrics computed per connected component:

- area lower/upper bounds and broad-blob area ratio,
- slenderness / aspect ratio (PCA on the component),
- orientation tolerance,
- local contrast across the component boundary band,
- broad-blob rejection (large, low-aspect, low-contrast regions).

The thresholds that affect formal A/B selection live in
`WireStripDetectorParams`, so a confirmed setup stores the exact filtering
recipe used by Run, Live Offline Run, and Offline Validation. The current
snapshot includes interval width/count gates, local-contrast minimum,
wire-likeness minimum, broad-blob and component-area limits, internal-gap limit,
and neighbor-line support. Orientation and aspect ratio are diagnostics/score
signals only in this phase; orientation is not a hard rejection gate.

`roi_ops` line scanning additionally caps the largest internal gap
(`_largest_gap_bounded_cluster`, configured by `max_internal_gap_px` or
`max_internal_gap_ratio`) so disjoint non-wire regions are never merged into one
bundle. The detector runs chord contact selection on the filtered
`wire_foreground`, so background blobs and low-contrast patches cannot extend
the formal `bundle_outer_span_px` / `formal_ab_span_px`.

## Phase 3 — Setup Wire Auto Tune

`vision/wire_auto_tune.py` (pure NumPy) sweeps candidate fixed thresholds
(baseline plus ROI histogram percentiles), runs the detector per candidate, and
scores each by validity, foreground-boundary support, local contrast,
neighbor-line support, wire-likeness, and rejection penalties. Candidate payloads
include the selected valid intervals, rejected interval count, broad-blob area,
local contrast, ROI margin, A/B boundary flags, failure reason, and score. It
selects the widest "stable platform" of adjacent thresholds and recommends its
representative.

Exposed through `services/setup_service.py` (`auto_tune_wire`) and
`POST /api/setup/wire-auto-tune`. `confirm` persists the chosen threshold into the
recipe and sets `MeasurementDefinition.auto_tuned = true`.

## Phase 4 — UI

`SetupPage` gains a Wire Auto Tune button (shown for `wire_strip`) that calls the
API, applies the recommended threshold to the segmentation controls, displays the
recommendation, stable platform, and per-candidate scores/reject reasons, and
marks the recipe as auto-tuned. Manual threshold controls remain for debugging;
editing them clears the auto-tuned flag.

## Phase 5 — Run / Offline Validation

- Run phase (`services/run_service.py`) applies the confirmed recipe verbatim per
  frame and re-detects the largest valid `formal_ab_span_px`. It never
  auto-tunes.
- `run_offline_threshold_sweep` (`services/offline_validation_service.py`)
  evaluates a recipe across candidate thresholds and writes
  `threshold_sweep_summary.json` with per-threshold valid ratio, interval stats,
  rejected-background (broad blob) stats, `formal_ab_span_px` stats, and
  distance/A-B jump stats. All path metadata is sanitized to labels.

## Tests

- `backend/tests/vision/test_wire_strip_detector_synthetic.py`: Phase 1
  diagnostics and Phase 2 broad-blob exclusion from the formal span.
- `backend/tests/vision/test_wire_auto_tune.py`: stable-platform recommendation
  and avoidance of thresholds that admit a broad blob.
- `backend/tests/api/test_setup_flow.py`: auto-tune endpoint and `auto_tuned`
  persistence.
- `backend/tests/validation/test_offline_validation_service.py`: per-threshold
  sweep stats and absolute-path sanitization.
- Frontend `vitest`: auto-tune client call, Setup UI, and result-panel fields.
