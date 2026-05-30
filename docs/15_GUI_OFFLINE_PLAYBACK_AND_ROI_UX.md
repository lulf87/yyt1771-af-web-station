# 15 — GUI Offline Playback and ROI UX

## Purpose

This phase makes the browser UI useful for checking real offline captures before any Hik MVS adapter work.

It keeps the existing static mock source for fast smoke tests, then adds a GUI path for real `.npy` frame folders, downsampled browser previews, hand-drawn ROI editing, A/B coordinate display, run overlays, and offline validation playback.

This phase does not change detector semantics. `BalloonEnvelopeDetector` and `WireStripDetector` remain the only public detectors. `wire_strip` remains contour-contact based, not endpoint based. OpenCV is still not introduced.

## Static Mock Scope

The built-in mock source is still available from Setup with `Open mock source`.

It is intentionally small and deterministic:

- frame size: `320 x 220`,
- image content: static synthetic grayscale target,
- use: smoke tests, automated tests, quick API/UI checks.

It does not represent real camera resolution, lighting, noise, motion, or dynamic A/B stability. Use real offline playback for those checks.

## Real Offline Source

Set the local frame folder with:

```bash
export YYT1771_AF_OFFLINE_DIR="/absolute/path/to/local/frames"
```

The folder can contain `.npy` frames such as:

```text
frame_000001.npy
frame_000002.npy
...
frame_005807.npy
```

The backend reads frames in natural order and loads images lazily. It uses `np.load(..., allow_pickle=False)` and supports 2D grayscale frames. API responses expose frame basenames and acquisition dimensions, but not the absolute local folder path.

## Browser Preview

The browser preview is a downsampled PNG. The formal coordinate system remains the original acquisition frame, such as `2048 x 1364`.

Current preview APIs:

```text
GET /api/camera/frame/latest?max_width=1200
GET /api/camera/frame/{frame_id}/preview.png?max_width=1200
GET /api/offline-playback/frame/{frame_index}/preview.png?max_width=1200
```

Metadata includes acquisition size, display size, scale values, frame index/name where available, and a preview URL. It does not include local absolute paths.

## Setup ROI Editing

On the Setup page:

1. Open `dev_offline` with `Open offline source`.
2. Freeze a frame.
3. Drag on the frame to create a new rectangular ROI.
4. Drag inside the ROI to move it.
5. Drag handles on the ROI edges/corners to resize it.
6. Use numeric fields for precise `center_x`, `center_y`, `width`, `height`, and `angle_deg`.
7. Run detection and inspect A/B overlay.

Mouse edits and numeric fields are synchronized. ROI values are stored in acquisition coordinates. The frontend only maps display coordinates to acquisition coordinates for ROI editing; it does not compute formal A/B points or `distance_px`.

## Result Panel

The Result panel shows:

- status,
- quality,
- distance_px,
- A x/y,
- B x/y,
- detector,
- coordinate space,
- reason.

If detection is invalid, A/B and distance show `N/A`; the UI does not invent coordinates.

## Run Overlay

The Run page includes a visual frame area for both Batch Run results and Live Offline Run.

Batch Run displays the latest stored sample after the synchronous batch returns. Live Offline Run displays each simulated camera frame as the browser requests it.

It displays:

- latest cached run frame preview,
- confirmed ROI,
- backend-returned A/B points,
- A/B line,
- status, distance, quality, and temperature summary.

Use Live Offline Run for dynamic inspection of many offline frames with per-frame detector execution. Use Offline Playback when reviewing existing offline validation outputs such as `evaluation_samples.jsonl`.

## Offline Playback Page

The Playback page replays real offline frames with detector/evaluation results.

Recommended workflow:

1. Run offline validation and generate `evaluation_samples.jsonl`:

```bash
python -m yyt1771_af.cli.offline_validate \
  --frames-dir "$YYT1771_AF_OFFLINE_DIR" \
  --target-family balloon_envelope \
  --config ./configs/validation/roi_balloon.example.json \
  --fps 10 \
  --output-dir ./validation_results/offline_eval_balloon_300 \
  --max-frames 300 \
  --overlay-top-jumps 20
```

2. Open the frontend.
3. Go to Playback.
4. Leave `Frames dir` blank to use `YYT1771_AF_OFFLINE_DIR`, or enter a local folder path.
5. Enter the evaluation output directory, for example:

```text
validation_results/offline_eval_balloon_300
```

6. Select the target family and open playback.
7. Use the slider, Prev/Next, Play/Pause, Failures only, and Top jumps buttons.

Playback loads sample metadata but fetches frame images on demand. It does not preload all frame images.

## Checking A/B Stability

Use `evaluation_summary.json` and the Playback page together:

- `top_jump_frames` identifies frames with large adjacent valid-frame jumps.
- `Failures only` isolates invalid frames.
- The overlay shows only backend/evaluation A/B points; the browser does not recompute them.
- A/B should remain on the intended contour, not ROI corners, crop edges, texture holes, or display pixels.

If A/B jumps are large or failure reasons are unexplained, keep improving ROI, recipe parameters, or detector internals before moving to real camera adapter work.

## Gate Before Hik MVS

Proceed toward Hik MVS adapter only when:

- real offline playback works at the target resolution,
- ROI can be drawn and adjusted reproducibly,
- A/B points are visually correct on representative frames,
- `valid_ratio` and status histogram are acceptable,
- top jump frames have been reviewed,
- processing speed is adequate for the intended sampling cadence.

The Hik MVS adapter remains intentionally unimplemented in this phase.
