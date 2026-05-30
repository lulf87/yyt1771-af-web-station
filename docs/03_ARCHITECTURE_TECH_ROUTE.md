# 03 — Architecture and Technical Route

## Architecture summary

The project is a browser UI plus Python backend.

```text
Browser UI
  ↓ HTTP / SSE / WebSocket later
FastAPI backend
  ↓ services
core models / geometry / vision
  ↓ interfaces
camera source / storage / report adapters
```

## Design principles

- Clean start. Do not reference previous code.
- Contracts first: models and tests before hardware.
- Offline/mock first: real hardware must not be required for development.
- Routes thin, services own use cases.
- Vision algorithms pure and unit-testable.
- Hardware adapters lazy-loaded and replaceable.
- Cross-platform by default.

## Recommended backend stack

- Python 3.11 or newer.
- FastAPI for HTTP API.
- Pydantic v2 for data models.
- NumPy for numerical arrays.
- OpenCV for image processing.
- PyYAML or pydantic-settings for configuration.
- pytest for tests.
- ruff for lint/format.

## Recommended frontend stack

- Vite.
- React.
- TypeScript.
- Canvas-based image preview and overlay.
- Simple state management first; do not add a large state library unless needed.
- Vitest for small frontend logic tests.

## Backend layer responsibilities

### `api/`

- FastAPI routers.
- Request/response conversion.
- No vision algorithms.
- No direct camera SDK calls.

### `services/`

- Application use cases.
- Setup flow.
- Run flow.
- Detection orchestration.
- Artifact writing.

### `core/`

- Pydantic models.
- Geometry types.
- Coordinate transforms.
- Error/status enums.
- No FastAPI imports.
- No camera SDK imports.

### `vision/`

- Pure image-processing functions.
- Target-specific detector implementations: `BalloonEnvelopeDetector` and `WireStripDetector`.
- Synthetic test helpers if useful.
- No FastAPI imports.
- No hardware imports.

### `camera/`

- Camera interface.
- Mock camera.
- Offline image/video source.
- Hik MVS adapter later.
- SDK import only inside the relevant adapter.

### `storage/`

- Local filesystem artifact store.
- JSON/CSV output.
- Later optional SQLite.

### `report/`

- Export functions.
- No direct camera or API dependencies.

## Frontend responsibilities

- Display current frame.
- Draw and edit rotated ROI.
- Select target family and recipe.
- Call setup detect API.
- Render backend-returned A/B points.
- Show status, quality, and failure reason.
- Start/stop runs when run service exists.

Frontend must not:

- run detection algorithms
- compute formal A/B points
- compute formal `distance_px`
- store display coordinates as measurement truth

## Runtime modes

### `dev_mock`

No hardware. Synthetic or generated frames.

### `dev_offline`

Read image files from a configured folder.

### `dev_lab`

Use real camera adapter and local configuration. Must be optional.

## Camera strategy

The first implementation must work without any camera SDK.

Real camera support must stay behind:

```python
class CameraSource:
    def open(self) -> None: ...
    def close(self) -> None: ...
    def get_latest_frame(self) -> Frame: ...
```

The Hik adapter must be lazy-loaded only when selected by profile. Mock and
offline modes must continue to run when the Hik SDK is absent.

## Storage strategy

MVP can store runs as local files:

```text
runs/{run_id}/
  run_definition.json
  samples.jsonl
  frames/              # optional later
  artifacts/
```

Avoid database until the data flow is stable.

## Configuration strategy

Use YAML profiles and recipes:

```text
configs/profiles/*.yaml
configs/recipes/*.yaml
configs/local/*.yaml  # ignored by git
```

Profiles define runtime source and paths.

Recipes define target-family detector parameters. The initial design has only two public detector kinds: `balloon_envelope_detector` and `wire_strip_detector`.
