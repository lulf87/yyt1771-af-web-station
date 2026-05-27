# AGENTS.md

## Project identity

This repository is a clean-start implementation of a YY/T 1771-style AF visual support tool.

Build a new project from these local documents only. Do not reference, inspect, copy, or import from any previous repository.

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
- No old-project references are introduced.
- macOS/Windows portability rules remain satisfied.
