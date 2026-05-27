# 08 — Development Plan

This plan is intended for Codex-driven implementation.

## Phase 0 — Repository scaffold

Create:

- backend package skeleton
- frontend skeleton
- configs
- tests folders
- lint/test configuration
- basic README

Acceptance:

- backend imports successfully
- frontend dev server can start
- no real hardware dependency
- health API returns ok

## Phase 1 — Core contracts and geometry

Implement:

- enums
- Pydantic models
- rotated ROI validation
- coordinate transform utilities
- Euclidean distance helper

Tests:

- ROI validation
- coordinate transform roundtrip
- Euclidean distance
- invalid model cases

Acceptance:

- all core tests pass
- no OpenCV required for pure geometry tests if avoidable

## Phase 2 — Synthetic target-specific detectors

Implement:

- synthetic image helper for tests
- ROI crop/rotation utilities
- basic segmentation
- two target-specific contour detectors
- target-family-specific preprocessing hooks

Tests:

- simple ellipse target
- rotated ellipse target
- ellipse with internal mesh/noise
- straight strip target
- rotated strip target
- invalid one-side-visible case
- contact-on-ROI-boundary case

Acceptance:

- both detectors return A/B on contour for valid synthetic cases
- both detectors return explicit status for invalid cases
- no hardware required

## Phase 3 — Setup API and offline frame source

Implement:

- mock camera source
- offline image folder source
- camera service
- setup freeze API
- setup detect API

Tests:

- health API
- open mock source
- freeze frame
- detect synthetic/offline frame

Acceptance:

- backend supports setup detection through HTTP

## Phase 4 — Minimal frontend setup page

Implement:

- image preview
- rotated ROI editor
- target-family selector
- detect button
- A/B overlay from backend response
- status/quality panel

Acceptance:

- user can load/freeze frame, draw ROI, run detection, and see A/B overlay

## Phase 5 — Run service MVP

Implement:

- confirmed recipe
- fixed-Hz mock/offline sampling loop
- saved samples JSONL
- run start/stop API
- samples API

Acceptance:

- run produces timestamped `distance_px` samples
- invalid frames record status and do not create fake distances

## Phase 6 — Hardware adapters

Implement after offline path is stable:

- Hik MVS adapter behind camera interface
- local config example
- no import failure when SDK absent

Acceptance:

- mock/offline tests still pass without SDK
- lab profile loads SDK only when selected

## Phase 7 — Analysis and export

Implement:

- run review page
- curve plotting
- CSV export
- PNG export
- XLSX export later

Acceptance:

- exported data includes frame/time/status/A/B/distance/quality
