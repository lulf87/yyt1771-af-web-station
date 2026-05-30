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
  "recipe_name": "balloon_envelope_default",
  "segmentation": {
    "polarity": "auto",
    "threshold_mode": "otsu",
    "threshold_value": null,
    "blur_kernel": 3,
    "close_kernel": 11,
    "open_kernel": 3,
    "min_component_area_px": 500,
    "fill_internal_holes": true
  },
  "detector": {
    "detector_kind": "balloon_envelope_detector",
    "envelope_mode": "solid_balloon",
    "contact_source": "filled_envelope",
    "min_quality": 0.65,
    "max_point_jump_px": 25.0,
    "reject_contact_on_roi_boundary": true,
    "boundary_margin_px": 4.0,
    "ignore_internal_texture": true,
    "fill_internal_holes": true,
    "bridge_mesh_gaps": true
  }
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
  "debug_overlay_url": "/api/setup/debug-overlay/dbg_abc123.png?max_width=1200",
  "diagnostics": {
    "contour_area_px": 123456.0,
    "candidate_components": 1,
    "envelope_mode": "solid_balloon",
    "configured_contact_source": "filled_envelope",
    "contact_source_used": "filled_envelope",
    "actual_contact_source_area_ratio": 0.62,
    "threshold_value": 196,
    "selected_polarity": "auto_dark_selected",
    "selected_reason": "preferred_point_dark",
    "raw_foreground_ratio": 0.36,
    "morphology_foreground_ratio": 0.48,
    "filled_envelope_ratio": 0.62,
    "measurement_line_y": 0.0,
    "detected_pattern": "mesh_outer_span",
    "raw_intervals": [{"start_local_x": -508.4, "end_local_x": -492.1, "width_px": 16.3}],
    "bridged_intervals": [{"start_local_x": -508.4, "end_local_x": -492.1, "width_px": 16.3}],
    "selected_valid_intervals": [{"start_local_x": -508.4, "end_local_x": -492.1, "width_px": 16.3}],
    "formal_point_a_source_interval": {"start_local_x": -508.4, "end_local_x": -492.1, "width_px": 16.3},
    "formal_point_b_source_interval": {"start_local_x": 602.2, "end_local_x": 613.6, "width_px": 11.4},
    "point_a_on_foreground_boundary": true,
    "point_b_on_foreground_boundary": true,
    "point_a_source_layer": "bridged_foreground",
    "point_b_source_layer": "bridged_foreground",
    "internal_gap_count": 8,
    "max_internal_gap_px": 72.0,
    "mesh_outer_span_px": 1122.0,
    "formal_ab_span_px": 1122.0,
    "virtual_envelope_span_px": 1230.0,
    "candidate_line_is_debug_only": false,
    "selected_component_bbox": {
      "min_x": 643,
      "min_y": 324,
      "max_x": 1765,
      "max_y": 1125
    },
    "left_margin_px": 105.7,
    "right_margin_px": 0.54,
    "top_margin_px": 12.3,
    "bottom_margin_px": 1.2,
    "fill_internal_holes_used": true
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
    "message": "Only one valid contour side found in ROI measurement direction.",
    "rejected_contact_side": "right",
    "distance_to_right_roi_boundary_px": 0.54,
    "boundary_margin_px": 4.0,
    "rejected_candidate_point_b": {
      "x": 1765.0,
      "y": 684.0,
      "coordinate_space": "acquisition"
    }
  }
}
```

`debug_overlay_url` returns a downsampled PNG visualization of the original frame,
ROI, foreground layers, selected contour, ROI margin lines, and debug-only
rejected contact candidates. It accepts boolean query parameters:
`show_raw_foreground`, `show_morphology_foreground`, `show_filled_envelope`,
`show_selected_contour`, and `show_rejected_candidates`. It must not contain
local filesystem paths.

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
  "recipe_name": "wire_strip_default",
  "segmentation": {
    "polarity": "auto",
    "threshold_mode": "adaptive",
    "threshold_value": null,
    "blur_kernel": 3,
    "close_kernel": 5,
    "open_kernel": 3,
    "min_component_area_px": 80,
    "fill_internal_holes": false
  },
  "detector": {
    "detector_kind": "wire_strip_detector",
    "measurement_model": "blank_wire_bundle_envelope_blank",
    "measurement_mode": "wire_bundle_envelope",
    "min_quality": 0.6,
    "max_point_jump_px": 20.0,
    "reject_contact_on_roi_boundary": true,
    "boundary_margin_px": 3.0,
    "require_physical_endpoints": false,
    "skeleton_endpoint_detection": false,
    "preserve_visible_strip_contour": true
  }
}
```

Response:

```json
{
  "measurement_definition_id": "md_abc123",
  "saved": true,
  "measurement_definition": {
    "measurement_definition_id": "md_abc123",
    "name": "run_recipe_001",
    "target_family": "wire_strip",
    "roi": {"center_x": 1000.0, "center_y": 680.0, "width": 800.0, "height": 260.0, "angle_deg": 12.0, "coordinate_space": "acquisition"},
    "recipe_name": "wire_strip_default",
    "segmentation": {"polarity": "auto", "threshold_mode": "adaptive", "threshold_value": null, "blur_kernel": 3, "close_kernel": 5, "open_kernel": 3, "min_component_area_px": 80, "fill_internal_holes": false},
    "detector": {"detector_kind": "wire_strip_detector", "measurement_model": "blank_wire_bundle_envelope_blank", "measurement_mode": "wire_bundle_envelope", "min_quality": 0.6, "max_point_jump_px": 20.0, "reject_contact_on_roi_boundary": true, "boundary_margin_px": 3.0, "require_physical_endpoints": false, "skeleton_endpoint_detection": false, "preserve_visible_strip_contour": true},
    "detector_version": "v1",
    "acquisition_frame_size": {"width": 2048, "height": 1364},
    "coordinate_space": "acquisition",
    "created_at_ms": 123456789
  }
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

## Live Offline Run

Live Offline Run is separate from batch Run. It simulates a live camera by stepping through a local offline frame folder and running the confirmed `MeasurementDefinition` on every requested frame.

No API response may echo local absolute paths.

### `POST /api/offline-run/open`

Request:

```json
{
  "measurement_definition_id": "md_abc123",
  "frames_dir": null,
  "fps": 10.0,
  "loop": true,
  "dataset_label": null,
  "start_frame_index": 0,
  "max_preview_width": 1200
}
```

If `frames_dir` is `null`, the backend reads `YYT1771_AF_OFFLINE_DIR`.

Response:

```json
{
  "session_id": "offline_run_abc123",
  "opened": true,
  "dataset_label": "local_frames",
  "frame_count": 5807,
  "current_frame_index": 0,
  "fps": 10.0,
  "loop": true,
  "measurement_definition_id": "md_abc123"
}
```

### `POST /api/offline-run/{session_id}/next`

Returns the next frame preview metadata and detection result. `previous` and `seek` return the same payload shape.

```json
{
  "session_id": "offline_run_abc123",
  "frame_index": 123,
  "frame_name": "frame_000124.npy",
  "relative_time_s": 12.3,
  "preview_url": "/api/offline-run/offline_run_abc123/frame/123/preview.png?max_width=1200",
  "acquisition_width": 2048,
  "acquisition_height": 1364,
  "display_width": 1200,
  "display_height": 799,
  "scale_x": 0.5859375,
  "scale_y": 0.58577713,
  "coordinate_space": "acquisition",
  "end_of_stream": false,
  "detection": {
    "status": "ok",
    "valid": true,
    "point_a": {"x": 714.8, "y": 789.4, "coordinate_space": "acquisition"},
    "point_b": {"x": 1726.8, "y": 789.4, "coordinate_space": "acquisition"},
    "distance_px": 1012.0,
    "quality": 0.95,
    "target_family": "balloon_envelope",
    "detector": "balloon_envelope_detector:v1",
    "diagnostics": {}
  },
  "runtime": {
    "run_mode": "live_offline",
    "recipe_locked": true,
    "source_type": "offline",
    "fps": 10.0,
    "loop": true
  }
}
```

Invalid frames keep formal A/B and `distance_px` as `null`. Rejected/debug candidates may appear only in diagnostics.

### Other Session Routes

```text
GET  /api/offline-run/{session_id}/status
POST /api/offline-run/{session_id}/previous
POST /api/offline-run/{session_id}/seek
POST /api/offline-run/{session_id}/close
GET  /api/offline-run/{session_id}/frame/{frame_index}/preview.png?max_width=1200
```
