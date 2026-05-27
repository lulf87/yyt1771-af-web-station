# 10 — Acceptance Checklist

Use this checklist when reviewing Codex-generated changes.

## General

- [ ] No old-project references.
- [ ] No copied old code.
- [ ] Code runs without real camera hardware.
- [ ] macOS/Windows portability rules are respected.
- [ ] No machine-specific paths committed.
- [ ] Public behavior matches docs.

## Backend

- [ ] API routes are thin.
- [ ] Business logic is in services.
- [ ] Vision logic is not inside FastAPI route functions.
- [ ] Hardware SDK imports are isolated and lazy.
- [ ] Pydantic models represent the documented contract.
- [ ] Failure statuses are explicit.

## Vision

- [ ] A/B points are contour contact points.
- [ ] `distance_px` is Euclidean pixel distance.
- [ ] Formal A/B points are in acquisition coordinates.
- [ ] `balloon_envelope` ignores internal mesh/texture where possible.
- [ ] `wire_strip` does not perform physical endpoint detection.
- [ ] Detector returns failure instead of fake points when evidence is insufficient.
- [ ] Synthetic tests cover valid and invalid cases.

## Frontend

- [ ] Frontend does not compute formal A/B points.
- [ ] Frontend draws backend-returned points only.
- [ ] Display transforms do not change stored acquisition coordinates.
- [ ] UI shows status and quality, not only distance.

## Storage

- [ ] Run data includes status, quality, A/B, and distance.
- [ ] Invalid samples do not invent `distance_px`.
- [ ] Runtime artifacts are ignored by git.

## Testing

- [ ] Backend tests pass.
- [ ] Frontend tests pass where implemented.
- [ ] Lint/format pass or failures are documented.
- [ ] Mock/offline mode has a manual smoke path.
