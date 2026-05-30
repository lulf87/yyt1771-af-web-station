# Detection Robustness and Auto Tuning

This document defines how the project should move from manual real-frame diagnosis toward robust setup-time auto tuning and safe run-time detection. It does not implement a Hik MVS adapter, does not add OpenCV, does not add a third public detector, and does not change the formal A/B point contract.

The immediate context is the real offline-frame experiment where `BalloonEnvelopeDetector` selected `auto_dark_selected` foreground, then the filled-envelope path expanded the selected region until the rejected candidate contacted the ROI right and bottom boundaries. Fixed-threshold trials such as 180, 160, and 140 are useful diagnostics, but they are not by themselves a validated production recipe.

## Scope and Non-Goals

The public detector contract remains:

- `BalloonEnvelopeDetector` for `balloon_envelope`
- `WireStripDetector` for `wire_strip`

`open_mesh` is an internal mode of `BalloonEnvelopeDetector`, not a new public detector. The formal A/B definition is same-line ROI-local chord contacts in acquisition coordinates. A and B must come from the same ROI-local measurement line, with local-y delta within the discrete pixel tolerance. Boundary rejection remains enabled. Rejected/debug candidates must never be stored or displayed as formal A/B points.

This document describes design and implementation planning only. It intentionally does not modify detection code.

## Why Fixed Threshold 160 Is Not a Long-Term Solution

A fixed threshold can make one frame or one lighting condition look better, but it is fragile because image intensity is not a stable physical unit:

- lamp brightness and camera exposure can drift,
- reflective fixtures and background panels can change local contrast,
- sample position can change the amount of dark mesh inside the ROI,
- material finish and wet/dry state can shift pixel intensity,
- acquisition gain or gamma settings can change the histogram even when the object geometry is unchanged.

If `threshold=160` is accepted only because it improves one screenshot, it may fail on the next sample, the next camera exposure, or a later part of the same 5807-frame sequence. It can also create false confidence: a valid status may appear while the selected contour still belongs partly to background, fixture, or ROI crop artifacts.

Fixed thresholds are acceptable as candidates inside a setup-time sweep. They are not acceptable as a universal default without validation across real offline frames and a manually reviewed golden set.

## Why Otsu Can Fail in Open Mesh Scenes

Otsu chooses a threshold from the intensity distribution. It works best when foreground and background form two clean histogram groups. Open mesh captures violate that assumption:

- the ROI contains dark strands, bright holes, shadows, fixtures, and background panels;
- foreground area can be sparse and fragmented;
- bright background holes may dominate the ROI histogram;
- dark non-target shadows can be connected to the mesh after morphology;
- filled-envelope processing can convert sparse mesh into a large blob;
- the optimal threshold for geometry may not match the histogram valley.

In this setting, Otsu may choose a plausible intensity split but still produce the wrong measurement contour. The setup process must evaluate geometric stability and boundary safety, not just histogram separation.

## Setup-Time Threshold Sweep and Auto Tune

Setup-time auto tuning should be an explicit calibration step after the user draws or imports an acquisition-coordinate ROI. It should run on a small representative set of frames, not only on a single frozen frame.

Recommended sources for tuning frames:

- the frozen setup frame,
- nearby offline frames around the setup frame,
- a short 30-frame smoke sample,
- optionally a 300-frame medium sample before full validation.

For `open_mesh`, the initial sweep should test:

- `polarity = dark_on_light`
- `fill_internal_holes = false`
- `contact_source = bridged_foreground`
- fixed threshold values from 120 to 190, with `160` only as an initial candidate, not a permanent default
- a small grid of `close_kernel`, `open_kernel`, and `min_component_area_px` around conservative defaults

The sweep must record every candidate result, including invalid results. It must not hide failed candidates, and it must not convert rejected/debug A/B points into formal points.

## Candidate Parameter Scoring

Auto tuning cannot select a recipe only because `status=ok`. A valid status is necessary but not sufficient. Each candidate should be scored from independent evidence:

- image quality precheck passes,
- valid ratio across tuning frames,
- raw foreground ratio stays within a plausible range,
- morphology foreground ratio does not jump far beyond raw ratio unless expected,
- filled-envelope ratio is not used for `open_mesh` contact selection,
- selected component bbox stays inside the ROI with margin,
- selected component does not touch unrelated top/bottom ROI boundaries,
- candidate component count is plausible for the mode,
- A/B points are formal valid points, not rejected/debug candidates,
- A/B points satisfy the same-line chord contract,
- `local_y_delta_px` and `parallel_error_px` remain inside tolerance,
- A/B jumps are small between adjacent valid frames,
- distance is stable across adjacent valid frames,
- result is insensitive to small threshold changes,
- processing time remains within offline validation expectations.

Suggested hard rejection gates:

- `status = caliper_contact_on_roi_boundary`
- formal `point_a`, `point_b`, or `distance_px` is null
- A/B are not on the same ROI-local measurement line
- `local_y_delta_px` or `parallel_error_px` exceeds tolerance
- selected component margin is below the configured boundary margin on the measurement side
- top or bottom margin is suspiciously small for a target expected to be centered inside the ROI
- foreground ratio is extremely high or extremely low for the selected mode
- threshold changes by one step produce large A/B or distance jumps

Suggested scoring terms:

- valid-ratio score over tuning frames,
- margin score from left/right/top/bottom ROI distances,
- area-ratio score from raw and bridged foreground ratios,
- bbox score from component position and size inside ROI,
- distance-stability score from mean and p95 adjacent-frame distance jumps,
- point-stability score from p95 A/B jumps,
- threshold-platform score from contiguous stable threshold range width,
- speed score from processing milliseconds per frame.

The selected recipe should maximize robust stability, not merely one-frame success.

## Threshold Stable Platform

A threshold stable platform is a contiguous range of threshold values where the detector behavior is materially unchanged.

For each threshold in the sweep, compute:

- valid ratio,
- status histogram,
- raw and bridged foreground ratios,
- selected component bbox,
- left/right/top/bottom ROI margins,
- A/B point jumps,
- local-y delta and parallel error,
- chord-length stability,
- distance mean and standard deviation,
- distance jump p95,
- count of boundary rejections,
- count of multiple-target or target-not-found results.

A threshold range is stable only if:

- valid ratio remains high across the range,
- distance mean changes slowly across adjacent threshold values,
- A/B points do not jump to a different component,
- A/B points remain on same-line ROI-local chords,
- chord length is stable across adjacent thresholds,
- ROI margins remain safely above boundary margin,
- top/bottom margins do not indicate crop-driven selection,
- status histogram is not dominated by invalid states,
- small threshold changes do not flip between valid and invalid.

Choose the center of the best stable platform, not the lowest or highest threshold at the edge. If no stable platform exists, setup must fail safely and require ROI, illumination, or detector-mode adjustment.

## Run-Time Recipe Locking

The run stage should normally lock the recipe confirmed during setup. This is important because run data must be interpretable: if threshold, polarity, morphology, or contact source can drift freely during measurement, later analysis cannot distinguish real sample deformation from detector parameter changes.

Run-time records should include the confirmed recipe identifier, parameter values, measurement model, and measurement mode. The run service should not silently auto-retune the detector or switch measurement model from frame to frame.

## Limited Run-Time Compensation

Limited compensation is allowed only when it stays inside the setup-confirmed stable platform and the quality precheck indicates a global imaging shift rather than a geometry change.

Allowed examples:

- adjust fixed threshold within the stable platform chosen during setup,
- apply a small exposure-normalized threshold offset when ROI contrast remains acceptable,
- mark a frame invalid but continue the run when a transient exposure issue occurs.

Must-invalid examples:

- threshold needed outside the stable platform,
- selected component touches ROI boundary,
- selected component bbox jumps to a different target or background region,
- same-line chord validation fails,
- A/B jump exceeds the confirmed stability envelope,
- distance jump is inconsistent with the expected physical process,
- contrast or exposure is outside setup-qualified range,
- saturation or background gradient invalidates segmentation,
- only rejected/debug candidates are available.

The default run-time behavior should be conservative: hold the recipe, evaluate quality, return invalid when trust is low, and never manufacture formal A/B points from rejected candidates.

## Default Strategy by Mode

### Solid Balloon

Recommended defaults:

- `polarity = auto` or validated target-specific polarity,
- `threshold_mode = otsu` as a candidate, not a guarantee,
- `fill_internal_holes = true`,
- `contact_source = filled_envelope`,
- boundary rejection enabled.

This mode assumes the target behaves like a solid outer envelope. Hole filling is appropriate only when internal holes represent texture/noise rather than the actual open structure.

### Open Mesh

Recommended initial defaults:

- `polarity = dark_on_light`,
- `threshold_mode = fixed` selected by setup sweep,
- setup threshold sweep from 120 to 190,
- `fill_internal_holes = false`,
- `contact_source = bridged_foreground`,
- conservative close/open morphology to bridge mesh gaps without swallowing background,
- boundary rejection enabled.

This remains an internal mode of `BalloonEnvelopeDetector`. It must use same-line ROI-local chord contacts after constructing a trustworthy contour source.

For `open_mesh`, `mesh_outer_span` means the outer-to-outer span from the leftmost valid mesh foreground interval to the rightmost valid mesh foreground interval on the selected contact source. It is not a virtual hull, not a filled-envelope edge, and not a ROI-boundary span. Internal mesh gaps may lie between A and B, but A and B themselves must snap to valid foreground interval boundaries. Future auto tune must reject candidates where either formal endpoint exists only on a debug/virtual envelope layer.

### Wire Strip

Recommended defaults:

- preserve visible strip/wire contour,
- do not use physical endpoint detection,
- do not fill holes to create a balloon-like envelope,
- use polarity and threshold strategy validated for the strip contrast,
- boundary rejection enabled.

`WireStripDetector` remains same-line chord based inside the ROI, not endpoint based. Its current formal pattern is `blank-wire_bundle_envelope-blank` and its only current formal measurement mode is `wire_bundle_envelope`.

For `wire_bundle_envelope`, one ROI-local measurement line may contain multiple valid wire foreground intervals. Internal gaps are wire-bundle spaces, not separate measurement objects and not inner-gap targets. Formal A/B are the left outer boundary of the leftmost valid wire interval and the right outer boundary of the rightmost valid wire interval. They must be real foreground-boundary points, not gap, background, ROI-boundary, virtual-envelope, or rejected/debug points.

Run-time wire detection chooses the current frame's valid candidate line with the largest `formal_ab_span_px`. Previous-frame `measurement_line_y`, A/B jump, and distance jump may be recorded for diagnostics and offline validation, but must not affect formal A/B selection in this stage.

## Image Quality Precheck

Before tuning or run detection, evaluate whether the frame is suitable for segmentation.

### Exposure

Track ROI pixel mean and percentile range. Reject or warn when the ROI is too dark, too bright, or shifted far outside the setup-qualified exposure range.

### Contrast

Track P95-P5 contrast inside the ROI and near the target band. Reject when contrast is too low to support foreground/background separation.

### Saturation

Count pixels near 0 and 255. A high saturation fraction can hide target geometry or make threshold sweeps meaningless.

### Background Gradient

Estimate whether one side of the ROI is much brighter or darker than another. A strong gradient can make one threshold select different physical regions across the ROI.

### ROI Margin

Check selected component margins to all four ROI sides. The existing left/right boundary protection remains required for formal contact points. Top/bottom margins should also be reported because they can reveal that the selected component has leaked into background or fixture regions even when the formal rejection side is left or right.

## Offline Validation of Auto Selection

Auto tuning should be validated in stages using the existing offline real-capture workflow.

### 30-Frame Smoke

Purpose:

- verify that the selected recipe runs,
- inspect overlays manually,
- confirm A/B points sit on the intended contour,
- check early status histogram and obvious failures.

Acceptance at this stage should be qualitative and conservative. It is a gate before spending time on longer runs.

### 300-Frame Medium Run

Purpose:

- estimate valid ratio,
- inspect top jump frames,
- compare distance and quality curves,
- verify the threshold platform holds beyond the setup frame,
- identify failure clusters from lighting, sample movement, or background changes.

This run is the first meaningful stability check.

### 5807-Frame Full Run

Purpose:

- measure long-sequence valid ratio,
- quantify A/B and distance jump distributions,
- quantify `local_y_delta_px`, `parallel_error_px`, and chord-length distributions,
- count pattern mismatches and object interval counts,
- detect time-varying exposure or background drift,
- verify processing fps,
- inspect representative failures and top jumps.

A full run can show stability over the captured sequence. It still cannot prove true geometric accuracy without manual ground truth.

## Stability Is Not Accuracy Without Labels

Without manual labels, offline validation can show that the detector is stable, fast, and safely invalidates suspicious frames. It cannot prove that A/B points are the true intended physical contact points.

A stable wrong contour can produce excellent-looking jump statistics. Therefore, auto tuning must be evaluated against a human-reviewed golden set before being treated as accurate.

## Golden Set Annotation Plan

Create a small manually annotated set from real offline frames:

- include clear valid frames,
- include boundary-contact failures,
- include lighting changes,
- include different sample positions,
- include frames where mesh and background are visually confusing,
- include frames from the beginning, middle, and end of the sequence,
- include top jump frames found by offline validation.

For each frame, record:

- frame basename only, not absolute path,
- target family and internal mode,
- ROI used,
- whether the frame should be valid,
- manually reviewed A point,
- manually reviewed B point,
- acceptable tolerance in pixels,
- reason for invalid label when invalid,
- reviewer name or review batch identifier.

Annotations should be stored as local or test-safe artifacts without raw `.npy` data in Git unless the frame is a synthetic or explicitly approved public fixture.

## Suggested Acceptance Metrics

Use these metrics separately for setup tuning, offline validation, and golden-set accuracy.

- `valid_ratio`: fraction of frames with formal valid detection.
- `false_valid_rate`: fraction of frames marked valid when the golden set says invalid.
- `A/B error`: distance from formal A/B to human labels on golden valid frames.
- `distance error`: absolute difference between detected and labeled A/B distance.
- `jump_p95`: p95 adjacent-frame A/B and distance jump over valid frames.
- `parallel_error_px`: A/B same-line parallel error; should stay within the pixel tolerance.
- `local_y_delta_px`: ROI-local y difference between A and B; should stay within the pixel tolerance.
- `chord_length_px`: same-line chord length stability.
- `mesh_outer_span_px`: open-mesh span from leftmost valid foreground interval to rightmost valid foreground interval.
- `bundle_outer_span_px`: wire-bundle span from leftmost valid wire foreground interval to rightmost valid wire foreground interval.
- `formal_ab_span_px`: formal A/B segment length; for open mesh this should match `mesh_outer_span_px`, not `virtual_envelope_span_px`.
- `virtual_envelope_span_px`: debug-only filled/hull span, never proof of formal A/B validity.
- `processing_fps`: effective frames per second for offline evaluation.

Suggested interpretation:

- high valid ratio is useful only if false valid rate is low,
- low jump p95 proves stability, not accuracy,
- A/B and distance error require manual labels,
- processing fps must be measured on the target development machines before deployment claims.

## Future Implementation Plan

This plan is intentionally staged so each step can be tested without changing the public detector contract.

### Step 1: Persist Robust Diagnostics

Files likely affected:

- `backend/src/yyt1771_af/core/models.py`
- `backend/src/yyt1771_af/vision/segmentation.py`
- `backend/src/yyt1771_af/vision/balloon_envelope_detector.py`
- `backend/src/yyt1771_af/vision/wire_strip_detector.py`
- `backend/tests/vision/`

Work:

- keep raw, bridged, and filled mask metrics available,
- add image quality precheck fields,
- add top/bottom warning fields where appropriate,
- test that invalid formal results remain null.

### Step 2: Add Setup Sweep Service

Files likely affected:

- `backend/src/yyt1771_af/services/`
- `backend/src/yyt1771_af/api/setup.py`
- `backend/tests/api/`
- `backend/tests/validation/`

Work:

- accept a candidate grid for threshold, polarity, fill holes, contact source, and morphology,
- run candidates over selected tuning frames,
- store candidate metrics without absolute frame paths,
- return ranked candidates and rejection reasons.

### Step 3: Add Stable Platform Selection

Files likely affected:

- `backend/src/yyt1771_af/services/`
- `backend/src/yyt1771_af/core/models.py`
- `backend/tests/validation/`

Work:

- group adjacent threshold candidates,
- compute platform width and sensitivity,
- choose the center of the best stable platform,
- fail setup when no stable platform exists.

### Step 4: Add Open Mesh Internal Mode

Files likely affected:

- `backend/src/yyt1771_af/core/models.py`
- `backend/src/yyt1771_af/vision/balloon_envelope_detector.py`
- `backend/tests/vision/test_balloon_envelope_detector_synthetic.py`
- `backend/tests/vision/test_detection_debug_diagnostics.py`

Work:

- add an internal `open_mesh` mode under `BalloonEnvelopeDetector`,
- default to `dark_on_light`,
- default to `fill_internal_holes=false`,
- use `bridged_foreground` as the initial contact source,
- keep boundary rejection unchanged,
- keep formal A/B definition unchanged.

### Step 5: Add Setup UI Auto Tune

Files likely affected:

- `frontend/src/pages/SetupPage.tsx`
- `frontend/src/components/SegmentationControls.tsx`
- `frontend/src/components/StatusPanel.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/api/types.ts`
- `frontend/src/components/*.test.tsx`

Work:

- add an Auto Tune action,
- show candidate ranking and rejection reasons,
- show stable threshold platform,
- require user confirmation before saving the recipe,
- keep manual controls available for diagnosis.

### Step 6: Validate Through Offline Runs

Files likely affected:

- `backend/src/yyt1771_af/services/offline_validation_service.py`
- `backend/src/yyt1771_af/cli/offline_validate.py`
- `backend/tests/validation/`
- `docs/14_OFFLINE_REAL_CAPTURE_VALIDATION.md`

Work:

- run 30-frame smoke, 300-frame medium, and full-sequence validation using the selected recipe,
- include tuning metadata in summaries without leaking local paths,
- inspect overlays for A/B correctness,
- compare against golden-set labels once available.

### Step 7: Define Release Gate Before Hik MVS

Files likely affected:

- `docs/10_ACCEPTANCE_CHECKLIST.md`
- `docs/14_OFFLINE_REAL_CAPTURE_VALIDATION.md`
- `docs/15_GUI_OFFLINE_PLAYBACK_AND_ROI_UX.md`

Work:

- require acceptable offline metrics,
- require golden-set review for accuracy claims,
- require documented invalid behavior for low-confidence frames,
- keep Hik MVS adapter work blocked until the offline recipe is stable and explainable.

## Decision Rule

Proceed toward live camera adaptation only when the offline pipeline can explain why a frame is valid, why a frame is invalid, and why the selected recipe remains stable under realistic variation. If the detector cannot explain the selected contour source, margins, threshold sensitivity, and A/B stability, it must fail safely rather than output a convenient measurement.
