# 09 — Test Plan

Testing starts before real hardware integration.

## Test pyramid

1. Core geometry unit tests.
2. Vision synthetic tests.
3. API tests with mock/offline sources.
4. Frontend component and geometry tests.
5. Manual lab hardware tests later.

## Core tests

### `test_geometry.py`

Required cases:

- Euclidean distance between two points.
- Rotated ROI corners are computed correctly.
- ROI angle 0, 45, 90 degrees.
- Invalid ROI width/height rejected.
- ROI outside frame returns invalid.

### `test_coordinates.py`

Required cases:

- acquisition → roi_local → acquisition roundtrip.
- acquisition → display transform for overlay.
- display transform never changes stored A/B values.

## Vision synthetic tests

Use generated images rather than lab photos for deterministic first tests.

### Balloon envelope

Cases:

- Solid ellipse, angle 0.
- Solid ellipse, rotated ROI.
- Ellipse with internal grid/mesh texture.
- Ellipse with small holes.
- Low contrast ellipse.
- Multiple objects in ROI.
- Object touches ROI boundary.

Expected:

- Valid cases return `ok`.
- A/B points lie on the external envelope.
- Internal mesh is not selected as A/B.
- Boundary touch returns explicit failure.

### Wire strip

Cases:

- Straight strip inside ROI.
- Rotated strip inside ROI.
- Curved strip section inside ROI.
- ROI contains only one visible edge.
- Strip contact lies on ROI crop boundary.
- Multiple strip-like objects.

Expected:

- Valid cases return `ok`.
- A/B points are opposite directional contour contacts.
- No endpoint search is performed.
- Invalid cases do not return fake `distance_px`.

## API tests

Use FastAPI test client.

Required cases:

- `GET /api/health` returns ok.
- mock camera opens.
- setup freeze returns frame ref.
- setup detect validates ROI.
- setup detect returns valid response for synthetic valid target.
- setup detect returns explicit failure for invalid ROI/target.

## Frontend tests

Required cases:

- Convert backend acquisition points to display overlay positions.
- ROI editor maintains acquisition coordinate model.
- Target-family selector sends valid enum values.

## Manual smoke tests

### Mock mode

- Start backend.
- Start frontend.
- Open setup page.
- Generate/freeze mock frame.
- Draw ROI.
- Detect.
- See A/B overlay and distance.

### Offline mode

- Configure image folder.
- Open offline source.
- Freeze frame.
- Detect target.

### Lab mode later

- Verify SDK load only with lab profile.
- Verify SDK absence does not break mock/offline mode.
- Verify frame dimensions and coordinate metadata.
