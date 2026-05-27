# 01 — Product Requirements

## Product name

Working name: `yyt1771-af-web-station`.

## Purpose

Build a browser-based station for supporting visual AF-point analysis in a YY/T 1771-style test workflow.

The application records image-derived pixel distance changes of a test object during recovery. The visual measurement is based on two contour contact points A/B inside a user-defined rotated ROI.

The project is a clean rewrite. It must not maintain compatibility with any previous codebase.

## Primary users

- Test operator: runs setup, draws ROI, chooses target type, starts/stops test, exports result.
- Engineer: validates detection behavior with offline images and synthetic cases.
- Developer: extends camera adapters, reports, and analysis methods.

## Main workflow

1. Select profile: mock, offline, or lab camera.
2. Open image source.
3. Freeze or select a setup frame.
4. Draw a rotated ROI around the target area.
5. Select target family:
   - `balloon_envelope`
   - `wire_strip`
6. Run detection preview.
7. Confirm measurement recipe.
8. Start run.
9. Capture repeated samples:
   - timestamp
   - optional temperature if available
   - point A
   - point B
   - `distance_px`
   - quality and status
10. Stop run.
11. Review curve and artifacts.
12. Export JSON/CSV/PNG/XLSX when implemented.

## MVP scope

The first working version must include:

- Cross-platform backend skeleton.
- Cross-platform frontend skeleton.
- Mock/offline image source.
- Typed data models.
- Rotated ROI model.
- Coordinate transform utilities.
- Synthetic image tests for detector behavior.
- Two target-specific contour detectors: `BalloonEnvelopeDetector` and `WireStripDetector`.
- Minimal setup API.
- Minimal UI that displays a frame and overlays ROI/A/B.

## Later scope

- Real Hik MVS camera adapter.
- Temperature device adapter.
- Run service with fixed sampling cadence.
- Report/export layer.
- AF analysis methods.
- Recipe editor.
- Camera-side ROI configuration.
- Artifact browser.

## Explicit non-goals for the first version

- No desktop GUI.
- No dependency on real camera SDK.
- No mandatory database.
- No millimeter calibration.
- No old-project compatibility.
- No physical endpoint detection for `wire_strip`.
- No full production-ready report in phase 1.

## Core measurement requirement

The primary measurement value is:

```text
distance_px = Euclidean distance between contour contact point A and contour contact point B
```

The system stores pixel distance only.

## Target families

### `balloon_envelope`

A whole-object target whose external envelope is the measurement object. Internal mesh, holes, markings, and texture must be ignored as much as possible.

### `wire_strip`

A visible strip/wire-like object inside the ROI. The algorithm measures contour contact points in the ROI measurement direction. It does not look for the physical endpoints of the whole wire.

## Quality requirement

Each detector must return explicit quality and failure information. It must not silently generate A/B points when contour evidence is unreliable.

## Platform requirement

The project must run on macOS and Windows. Platform-specific code is allowed only in hardware adapters and local runtime configuration.
