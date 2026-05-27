# Prompt 01 — Initial Scaffold

Read `AGENTS.md` and all documents under `docs/` in numeric order.

Build the initial repository scaffold for this clean-start project. Do not reference or copy any previous project.

Before writing code, produce a concise plan listing:

- files you will create
- commands you expect to add
- tests you will implement
- assumptions and risks

Then implement the scaffold.

## Required output

Create a minimal but runnable project with:

1. Backend Python package under `backend/src/yyt1771_af/`.
2. FastAPI app with `GET /api/health`.
3. Core data models from `docs/06_DATA_MODEL_CONTRACT.md`.
4. Geometry helpers for Euclidean distance and basic ROI validation.
5. Backend tests for health, models, and geometry.
6. Frontend Vite + React + TypeScript skeleton under `frontend/`.
7. Basic setup page placeholder.
8. Root README with run instructions.
9. Lint/test configuration where practical.

## Constraints

- The project must run without real camera SDKs.
- Do not implement Hik MVS adapter beyond an interface placeholder.
- Do not implement full detector yet unless it is small and tested.
- Use `pathlib.Path` for paths.
- Do not hard-code OS-specific paths.
- Keep the implementation small and reviewable.

## Verification

After implementation, run the relevant tests or explain exactly why they could not be run.
