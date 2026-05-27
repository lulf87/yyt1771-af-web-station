# 05 — API Contract

The API contract is intentionally small for the initial project.

## General rules

- API routes are thin.
- All formal geometry uses `acquisition` coordinates.
- Responses include explicit status and error details.
- Detection APIs return backend-computed A/B points.
- Frontend must not compute formal A/B points.

## Health

### `GET /api/health`

Response:

```json
{
  "ok": true,
  "app": "yyt1771-af-web-station",
  "version": "0.1.0"
}
```

## Camera/source

### `GET /api/camera/status`

Response:

```json
{
  "opened": true,
  "source_type": "offline",
  "latest_frame_id": 12,
  "frame_width": 2048,
  "frame_height": 1364,
  "coordinate_space": "acquisition"
}
```

### `POST /api/camera/open`

Request:

```json
{
  "profile": "dev_offline"
}
```

Response:

```json
{
  "opened": true,
  "source_type": "offline"
}
```

### `POST /api/camera/close`

Response:

```json
{
  "opened": false
}
```

### `GET /api/camera/frame/latest`

Returns the latest preview image or frame metadata.

Initial implementation may return JSON metadata plus a separate image endpoint.

Suggested response:

```json
{
  "frame_id": 12,
  "timestamp_ms": 123456789,
  "width": 2048,
  "height": 1364,
  "coordinate_space": "acquisition",
  "preview_url": "/api/camera/frame/12/preview.png"
}
```

## Setup

### `POST /api/setup/freeze`

Captures or selects a setup frame.

Request:

```json
{
  "source": "latest"
}
```

Response:

```json
{
  "frame_ref": {
    "frame_id": 12,
    "timestamp_ms": 123456789,
    "width": 2048,
    "height": 1364,
    "coordinate_space": "acquisition"
  },
  "preview_url": "/api/camera/frame/12/preview.png"
}
```

### `POST /api/setup/detect`

Runs detection on a setup frame.

Request:

```json
{
  "frame_ref": {
    "frame_id": 12,
    "timestamp_ms": 123456789,
    "width": 2048,
    "height": 1364,
    "coordinate_space": "acquisition"
  },
  "roi": {
    "center_x": 1000.0,
    "center_y": 680.0,
    "width": 800.0,
    "height": 260.0,
    "angle_deg": 12.0,
    "coordinate_space": "acquisition"
  },
  "target_family": "balloon_envelope",
  "recipe_name": "balloon_envelope_default"
}
```

Successful response:

```json
{
  "status": "ok",
  "valid": true,
  "point_a": {"x": 620.4, "y": 700.2, "coordinate_space": "acquisition"},
  "point_b": {"x": 1388.7, "y": 864.5, "coordinate_space": "acquisition"},
  "distance_px": 785.1,
  "quality": 0.93,
  "target_family": "balloon_envelope",
  "detector": "balloon_envelope_detector:v1",
  "diagnostics": {
    "contour_area_px": 123456.0,
    "candidate_components": 1
  }
}
```

Failure response:

```json
{
  "status": "opposing_contour_edges_missing",
  "valid": false,
  "point_a": null,
  "point_b": null,
  "distance_px": null,
  "quality": 0.22,
  "target_family": "wire_strip",
  "detector": "wire_strip_detector:v1",
  "diagnostics": {
    "message": "Only one valid contour side found in ROI measurement direction."
  }
}
```

### `POST /api/setup/confirm`

Saves the measurement recipe for a run.

Request:

```json
{
  "name": "run_recipe_001",
  "target_family": "wire_strip",
  "roi": {
    "center_x": 1000.0,
    "center_y": 680.0,
    "width": 800.0,
    "height": 260.0,
    "angle_deg": 12.0,
    "coordinate_space": "acquisition"
  },
  "recipe_name": "wire_strip_default"
}
```

Response:

```json
{
  "recipe_id": "recipe_001",
  "saved": true
}
```

## Runs

### `POST /api/runs/start`

Request:

```json
{
  "recipe_id": "recipe_001",
  "sample_hz": 10.0
}
```

Response:

```json
{
  "run_id": "run_2026_001",
  "started": true
}
```

### `GET /api/runs/{run_id}/events`

Initial implementation may use polling. Later use SSE.

Event payload:

```json
{
  "run_id": "run_2026_001",
  "sample_index": 42,
  "timestamp_ms": 123456999,
  "temperature_c": 37.2,
  "status": "ok",
  "point_a": {"x": 620.4, "y": 700.2, "coordinate_space": "acquisition"},
  "point_b": {"x": 1388.7, "y": 864.5, "coordinate_space": "acquisition"},
  "distance_px": 785.1,
  "quality": 0.93
}
```

### `POST /api/runs/{run_id}/stop`

Response:

```json
{
  "run_id": "run_2026_001",
  "stopped": true
}
```

### `GET /api/runs/{run_id}/samples`

Returns saved samples.

### `GET /api/runs/{run_id}/artifacts`

Returns available artifacts.
