# Prompt 03 — Phase 2 Web Setup Flow

Implement the minimal setup flow connecting frontend and backend.

Read:

- `docs/05_API_CONTRACT.md`
- `docs/02_DETECTION_CONTRACT.md`
- `docs/04_PROJECT_STRUCTURE.md`

## Required backend behavior

- Mock camera source.
- Offline folder source if straightforward.
- `POST /api/camera/open`.
- `GET /api/camera/status`.
- `POST /api/setup/freeze`.
- `POST /api/setup/detect`.

## Required frontend behavior

- Display latest/frozen frame.
- Allow rotated ROI input or simple editor.
- Select target family.
- Call setup detect API.
- Render backend-returned A/B points.
- Show status, quality, and distance.

## Constraints

- Frontend must not compute formal A/B points.
- Frontend must keep measurement geometry in acquisition coordinates.
- No real hardware required.
