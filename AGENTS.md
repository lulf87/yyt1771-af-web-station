# AGENTS.md

## Project identity

This repository is a clean-start implementation of a YY/T 1771-style AF visual support tool.

Build a new project from these local documents only. Do not reference, inspect, copy, or import from any previous repository.

Exception for validation material only: user-approved offline camera capture frames may be read from the local legacy runtime folder listed under "Local validation material". This exception is limited to raw `.npy`/`.pgm` frames and associated capture metadata needed for Live Offline Run, Offline Validation, Playback, Analysis, and Export checks. Do not inspect, copy, import, or reuse code from the legacy project.

## Read first

Before making changes, read these files in order:

1. `00_CODEX_START_HERE.md`
2. `docs/01_PRODUCT_REQUIREMENTS.md`
3. `docs/02_DETECTION_CONTRACT.md`
4. `docs/03_ARCHITECTURE_TECH_ROUTE.md`
5. `docs/04_PROJECT_STRUCTURE.md`
6. `docs/05_API_CONTRACT.md`
7. `docs/06_DATA_MODEL_CONTRACT.md`
8. `docs/07_CROSS_PLATFORM_REQUIREMENTS.md`
9. `docs/08_DEVELOPMENT_PLAN.md`
10. `docs/09_TEST_PLAN.md`
11. `docs/10_ACCEPTANCE_CHECKLIST.md`

## Core product rules

- The application is a Web UI plus Python backend.
- The project must support macOS and Windows.
- The first working version must run without real camera hardware.
- Real camera SDK imports must be isolated behind lazy-loaded adapters.
- Vision algorithms must be testable without FastAPI, browser UI, hardware, or filesystem side effects.
- All formal ROI, A/B points, and `distance_px` values are stored in `acquisition` coordinates.
- Main measurement value is Euclidean pixel distance between A and B.
- Do not implement physical endpoint detection for `wire_strip` unless a future requirement explicitly changes the detection contract.

## Detection rules

The project has exactly two public detector implementations:

- `BalloonEnvelopeDetector` for `balloon_envelope`
- `WireStripDetector` for `wire_strip`

Do not create a third public detector in the initial version.

Both detectors use the ROI measurement direction to select A/B as contour contact points on opposite support sides.

- A/B must lie on valid target contour points, not on display pixels, ROI box corners, bounding-box corners, internal texture, mesh holes, or projected-only mathematical points.
- `balloon_envelope` uses an outer envelope contour and ignores internal mesh/texture.
- `wire_strip` uses the visible strip/wire-like contour inside the ROI and does not require physical wire endpoints.
- Shared ROI/projection helper functions are allowed, but product behavior and diagnostics must remain target-specific.

## Engineering rules

- Keep API routes thin. Put business logic in services.
- Keep hardware access behind interfaces.
- Keep geometry and vision code pure and unit-testable.
- Avoid global mutable state except controlled runtime services.
- Prefer typed models and explicit enums.
- Add or update tests for each behavior change.
- Use small, reviewable commits or changesets.

## Cross-platform rules

Do not hard-code:

- `/tmp`, `/dev/...`, `/Users/...`
- `C:\...`
- local SDK paths
- platform-specific shell commands
- path separators

Use:

- `pathlib.Path`
- environment variables
- profile-based config
- ignored local config files
- Python module entrypoints
- cross-platform npm scripts

## Local validation material

The following local folders are approved read-only offline capture material for this workstation:

- `/Users/lulingfeng/Documents/工作/开发/奥氏体变换/1771/yyt1771_starter/examples/runtime/camera_captures/20260522-183158-dev_lab/frames`
  - 5807 `.npy`/`.pgm` frames
  - capture metadata is in the parent folder, including `manifest.json` and `temperature.csv`
- `/Users/lulingfeng/Documents/工作/开发/奥氏体变换/1771/yyt1771_starter/examples/runtime/camera_captures/20260529-194304-dev_lab/frames`
  - 8623 `.npy`/`.pgm` frames
  - capture metadata is in the parent folder, including `manifest.json` and `temperature.csv`

Rules for this material:

- Treat it as immutable raw data: do not edit, rename, move, delete, regenerate, or commit copies of these files.
- It may be used to verify Live Offline Run stability, trace diagnostics, FPS profiling, Offline Validation, Playback, Analysis, and Export behavior.
- Configure it through environment variables such as `YYT1771_AF_OFFLINE_DIR` or ignored local config such as `configs/local/offline_datasets.local.json`.
- Do not hard-code these absolute paths in application code, tests, API responses, diagnostics payloads, committed cross-platform docs, or logs returned to the frontend.
- API responses and diagnostics must expose only sanitized labels or frame basenames, never the local capture path.

## Suggested implementation stack

Backend:

- Python 3.11+
- FastAPI
- Pydantic v2
- NumPy
- OpenCV
- PyYAML or pydantic-settings
- pytest
- ruff
- mypy or pyright if practical

Frontend:

- Vite
- React
- TypeScript
- Canvas overlay for ROI and A/B visualization
- Vitest for frontend logic where useful

## Before coding

For complex or multi-file tasks, produce a concise plan first. Include:

- files to create/change
- test strategy
- assumptions
- risks

Then implement after the plan.

## Definition of done

A task is done only when:

- Code matches the relevant docs.
- Tests are added or updated.
- Tests and lint pass or failures are clearly explained.
- Every fix is confirmed in a real browser when it affects the Web UI or user-facing API flow; report the browser URL, action taken, and observed result. If browser confirmation is impossible, state the blocker explicitly.
- No old-project references are introduced, except the approved read-only validation material listed above.
- macOS/Windows portability rules remain satisfied.
