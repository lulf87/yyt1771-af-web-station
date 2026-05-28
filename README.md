# YYT1771 AF Web Station

Browser UI plus Python backend for supporting YY/T 1771-style AF visual measurement workflows.

The current version runs without real camera hardware. It supports mock frames, offline `.npy`/PGM frame folders, contour-based A/B detection for the two public detector families, setup/run/analysis/export flows, temperature mock support, and an Offline Real-Capture Validation workflow for checking real captured frame folders before Hik MVS integration.

## Current Scope

- FastAPI backend under `backend/src/yyt1771_af`.
- Vite React TypeScript frontend with setup, run, and analysis pages.
- GUI source selection for both `dev_mock` and `dev_offline`.
- Two public detector implementations only:
  - `BalloonEnvelopeDetector`
  - `WireStripDetector`
- Formal ROI, A/B points, and `distance_px` stored in `acquisition` coordinates.
- Mock camera source for deterministic local development.
- Offline camera source for lazy streaming of `.npy` and PGM frame folders.
- Offline Real-Capture Validation service and CLI.
- Dataset manifest, per-frame JSONL/CSV samples, summary JSON, curves, histogram, jump report, and optional debug overlays.
- JSON and YAML config loading for profiles, recipes, and offline validation configs.
- Template ROI/config files under `configs/validation/` and `configs/local/`.
- JSON, CSV, PNG, and XLSX run export paths with local path redaction.
- Temperature controller abstraction with mock/file/serial-placeholder paths.
- Hik MVS real camera adapter is still intentionally deferred.

## Requirements

- Python 3.11 or newer.
- Node.js 20 or newer is recommended for Vite 7.
- No camera SDK is required for mock/offline/validation workflows.

## Backend Setup

Create and activate a virtual environment with your preferred cross-platform workflow, then install the backend package with development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run backend tests:

```bash
python -m pytest
```

Run backend lint and format checks:

```bash
python -m ruff check backend/src backend/tests
python -m ruff format --check backend/src backend/tests
```

Start the backend development server:

```bash
python -m uvicorn yyt1771_af.main:app --reload
```

Health check:

```text
GET http://127.0.0.1:8000/api/health
```

Expected response:

```json
{"ok": true, "app": "yyt1771-af-web-station", "version": "0.2.0"}
```

## Frontend Setup

Install frontend dependencies:

```bash
npm --prefix frontend install
```

Start the frontend development server:

```bash
npm --prefix frontend run dev
```

In the Setup page, use `Open mock source` for generated frames or `Open offline source` for a configured local offline frame folder.

Build and check the frontend:

```bash
npm --prefix frontend run test
npm --prefix frontend run lint
npm --prefix frontend run build
```

## Offline Real-Capture Validation

Set the local offline frame folder through an environment variable. The path is local-only and must not be committed:

```bash
export YYT1771_AF_OFFLINE_DIR="/absolute/path/to/local/frames"
```

Use a JSON or YAML ROI/config file in acquisition coordinates. Committed examples:

```text
configs/validation/offline_real_capture.example.json
configs/validation/offline_real_capture.example.yaml
configs/validation/roi_balloon.example.json
configs/validation/roi_wire.example.json
```

Run a 30-frame smoke test:

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

Run a 300-frame evaluation:

```bash
python -m yyt1771_af.cli.offline_validate \
  --frames-dir "$YYT1771_AF_OFFLINE_DIR" \
  --target-family wire_strip \
  --config ./configs/validation/roi_wire.example.json \
  --fps 10 \
  --output-dir ./validation_results/offline_eval_wire_300 \
  --max-frames 300 \
  --overlay-every 100 \
  --overlay-failures
```

Run the full folder by omitting `--max-frames`:

```bash
python -m yyt1771_af.cli.offline_validate \
  --frames-dir "$YYT1771_AF_OFFLINE_DIR" \
  --target-family balloon_envelope \
  --config ./configs/validation/roi_balloon.example.json \
  --fps 10 \
  --output-dir ./validation_results/offline_eval_balloon_full \
  --overlay-top-jumps 20
```

Each evaluation writes:

```text
evaluation_manifest.json
evaluation_samples.csv
evaluation_samples.jsonl
evaluation_summary.json
distance_curve.png
quality_curve.png
status_histogram.png
point_jump_summary.json
overlays/
```

Use `evaluation_summary.json`, `point_jump_summary.json`, and overlays to decide whether A/B is stable enough to proceed toward real Hik MVS adapter work.

## Configs

Backend config files can be JSON, YAML, or YML:

```text
configs/profiles/*.yaml
configs/recipes/*.yaml
configs/validation/*.json
configs/validation/*.yaml
configs/local/*              # ignored local machine config
```

Profiles define runtime source settings. Recipes define target-family detector parameters. Offline validation configs combine target family, ROI, optional recipe name, fps, dataset label, and optional local paths.

## Root Scripts

The root `package.json` exposes convenience commands:

```bash
npm run backend:test
npm run backend:lint
npm run backend:format:check
npm run frontend:dev
npm run frontend:build
npm run frontend:test
npm run frontend:lint
npm run test
npm run lint
```

## Project Rules

- Do not reference or copy old project code.
- Keep formal ROI, A/B points, and `distance_px` in `acquisition` coordinates.
- Frontend must not compute formal A/B points or formal distance.
- Real camera SDK imports must stay isolated behind lazy-loaded adapters.
- Do not create a third public detector.
- Do not change `wire_strip` into physical endpoint detection.
- Raw data and machine-specific config files must not be edited in place or committed.
