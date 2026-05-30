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
POST /api/offline-run/{session_id}/previous
POST /api/offline-run/{session_id}/seek
POST /api/offline-run/{session_id}/close
GET  /api/offline-run/{session_id}/frame/{frame_index}/preview.png?max_width=1200
```

The `preview_url` always includes the session id so multiple sessions cannot cross-read different datasets.

## Run Page Workflow

1. Start backend and frontend.
2. In Setup, open the offline source, freeze a frame, draw ROI, tune recipe, and confirm setup.
3. Go to Run.
4. Select `Live Offline Run`.
5. Click `Open Live Source`.
6. Use `Play`, `Pause`, `Step Prev`, `Step Next`, and `Seek`.
7. Adjust FPS and Loop before opening the session.

The frame preview is downsampled for the browser. Formal ROI and A/B coordinates remain in the original acquisition frame size.

## Overlay Rules

When `valid = true`:

- draw the confirmed ROI,
- draw FORMAL A/B points,
- draw only the formal A-to-B segment,
- do not show rejected/debug candidates as formal points.

When `valid = false`:

- draw the confirmed ROI,
- do not draw formal A/B,
- optionally draw rejected/debug candidates with rejected/debug styling,
- keep `distance_px` as `N/A`.

## Hik MVS Boundary

Live Offline Run is still offline-only. It does not implement, import, or configure Hik MVS. Real camera adapter work remains deferred.
