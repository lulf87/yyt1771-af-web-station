# 14 — Offline Real-Capture Validation

## Purpose

This phase validates the current ROI, detector, A/B contact-point selection, failure statuses, and processing speed against real camera-captured offline `.npy` frames before any Hik MVS live-camera adapter is implemented.

The goal is not to change detector semantics. `BalloonEnvelopeDetector` and `WireStripDetector` remain the only public detectors. `wire_strip` remains contour-contact based and must not become endpoint detection.

## Why This Comes Before Hik MVS

Real offline frames expose lighting, contrast, texture, noise, and stability issues without adding live camera SDK risk. Running the existing detectors over a full recorded sequence gives objective evidence for:

- valid/invalid frame ratio,
- status and failure distribution,
- A/B point jump behavior,
- distance and quality curves,
- processing fps,
- debug overlays for manual contour-contact inspection.

Only after this evidence is acceptable should the project move to Hik MVS live-camera integration.

## Data Protection Rules

Real `.npy` frame data must not be committed to Git.

Ignored locations include:

- `local_data/`
- `camera_captures/`
- `sample_data/local/`
- `validation_results/`
- `offline_eval_results/`
- `*.npy`

Tests must generate `.npy` data dynamically under pytest temporary directories. Do not add real `.npy` fixtures.

## Frames Directory

Set the local frames directory with:

```bash
export YYT1771_AF_OFFLINE_DIR="/absolute/path/to/local/frames"
```

The CLI also accepts `--frames-dir`. If omitted, it reads `YYT1771_AF_OFFLINE_DIR`.

Artifacts never store this absolute path. They store a dataset label, frame basenames such as `frame_000001.npy`, counts, and relative artifact names.

## ROI Config JSON/YAML

ROI config files can be JSON, YAML, or YML. ROI values must use acquisition coordinates:

```json
{
  "target_family": "balloon_envelope",
  "roi": {
    "center_x": 1024.0,
    "center_y": 682.0,
    "width": 800.0,
    "height": 300.0,
    "angle_deg": 0.0,
    "coordinate_space": "acquisition"
  },
  "recipe": {
    "name": "offline_real_capture_baseline"
  }
}
```

The equivalent YAML form is also supported:

```yaml
target_family: balloon_envelope
roi:
  center_x: 1024.0
  center_y: 682.0
  width: 800.0
  height: 300.0
  angle_deg: 0.0
  coordinate_space: acquisition
recipe:
  name: offline_real_capture_baseline
fps: 10.0
dataset_label: offline_real_capture_example
```

For wire validation:

```json
{
  "target_family": "wire_strip",
  "roi": {
    "center_x": 1024.0,
    "center_y": 682.0,
    "width": 800.0,
    "height": 300.0,
    "angle_deg": 0.0,
    "coordinate_space": "acquisition"
  }
}
```

Initial local templates are provided at:

- `configs/validation/offline_real_capture.example.json`
- `configs/validation/offline_real_capture.example.yaml`
- `configs/validation/roi_balloon.example.json`
- `configs/validation/roi_wire.example.json`

Copy them into `configs/local/` or another ignored local location, then adjust `center_x`, `center_y`, `width`, `height`, and `angle_deg` from the first frame. The CLI rejects ROI values outside the frame bounds. `--roi-json` remains a backward-compatible alias, but new commands should use `--config`.

## Smoke Test: 30 Frames

```bash
python -m yyt1771_af.cli.offline_validate \
  --frames-dir "$YYT1771_AF_OFFLINE_DIR" \
  --target-family balloon_envelope \
  --config ./configs/validation/roi_balloon.example.json \
  --fps 10 \
  --output-dir ./validation_results/offline_eval_balloon_smoke \
  --max-frames 30 \
  --overlay-first 10
```

Use this to verify ROI placement, basic detection status, and overlay rendering.

## Medium Test: 300 Frames

```bash
python -m yyt1771_af.cli.offline_validate \
  --frames-dir "$YYT1771_AF_OFFLINE_DIR" \
  --target-family wire_strip \
  --config ./configs/validation/roi_wire.example.json \
  --fps 10 \
  --output-dir ./validation_results/offline_eval_wire_300 \
  --max-frames 300 \
  --overlay-first 10 \
  --overlay-every 100 \
  --overlay-failures \
  --overlay-top-jumps 20
```

Use this to assess stability before committing to the full run.

## Full Run: All Frames

Omit `--max-frames`:

```bash
python -m yyt1771_af.cli.offline_validate \
  --frames-dir "$YYT1771_AF_OFFLINE_DIR" \
  --target-family balloon_envelope \
  --config ./configs/validation/roi_balloon.example.json \
  --fps 10 \
  --output-dir ./validation_results/offline_eval_balloon_full \
  --overlay-first 10 \
  --overlay-every 500 \
  --overlay-failures \
  --overlay-top-jumps 20
```

The evaluator processes as fast as possible. `fps` is used only for logical `relative_time_s = frame_index / fps`; it does not sleep at 10 fps.

## Output Files

Each evaluation writes:

- `evaluation_manifest.json`
- `evaluation_samples.csv`
- `evaluation_samples.jsonl`
- `evaluation_summary.json`
- `distance_curve.png`
- `quality_curve.png`
- `status_histogram.png`
- `point_jump_summary.json`
- `overlays/*.png` when overlay options select frames

## Reading Results

Start with `evaluation_summary.json`:

- `valid_ratio`: fraction of processed frames with valid detection.
- `status_counts`: all detection statuses, including invalid frames.
- `top_failure_reasons`: most frequent explicit failure reasons.
- `mean_processing_ms`, `p95_processing_ms`, `effective_processing_fps`: processing speed.
- `distance_px_*`: distance curve statistics over valid frames.
- `point_a_jump_px_*`, `point_b_jump_px_*`, `distance_jump_px_*`: adjacent valid-frame jump statistics.
- `top_jump_frames`: frames to inspect first for A/B instability.

Use `distance_curve.png`, `quality_curve.png`, and `status_histogram.png` for quick visual review. Use CSV/JSONL as the source of truth.

## Debug Overlays

Overlay PNGs show:

- ROI,
- detector-returned A point,
- detector-returned B point,
- A/B line,
- frame index,
- status,
- distance,
- quality,
- reason.

Overlay generation never recomputes formal A/B points. It only draws acquisition-coordinate values returned by the detector.

Useful options:

- `--overlay-first 10`
- `--overlay-every 100`
- `--overlay-failures`
- `--overlay-top-jumps 20`

## Decision Gate Before Hik MVS

Do not start Hik MVS adapter work until offline validation shows:

- ROI is correctly placed over the target family.
- A/B points sit on the intended contour in overlays.
- `valid_ratio` is acceptable for the test material.
- status histogram failures are understood.
- A/B jump statistics do not show unexplained large discontinuities.
- processing fps is adequate for the intended sampling rate.

If results are poor, improve detector internals or recipes first. If OpenCV is later introduced, it must remain an internal implementation detail of the two existing public detectors.
