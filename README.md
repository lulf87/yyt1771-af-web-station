# YYT1771 AF Web Station

Browser UI plus Python backend for supporting YY/T 1771-style AF visual measurement workflows.

This is a clean-start project. The first scaffold runs without real camera hardware and prepares the contracts for mock/offline image sources, rotated ROI handling, and target-specific detector work in later phases.

## Current Scope

- FastAPI backend package under `backend/src/yyt1771_af`.
- `GET /api/health` endpoint.
- Pydantic v2 core data models from `docs/06_DATA_MODEL_CONTRACT.md`.
- Geometry helpers for Euclidean distance, ROI measurement direction, ROI corners, and frame-boundary validation.
- Backend tests for health, models, and geometry.
- Vite React TypeScript frontend skeleton with a setup page shell.
- Camera SDK integration is intentionally deferred.

## Requirements

- Python 3.11 or newer.
- Node.js 20 or newer is recommended for Vite 7.
- No camera SDK is required for the scaffold.

## Backend Setup

Create and activate a virtual environment with your preferred cross-platform workflow, then install the backend package with development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run backend tests:

```bash
python -m pytest
```

Run backend lint and format checks:

```bash
python -m ruff check backend
python -m ruff format --check backend
```

Start the backend development server:

```bash
python -m uvicorn yyt1771_af.main:app --reload
```

Health check:

```text
GET http://127.0.0.1:8000/api/health
```

Expected response:

```json
{"ok": true, "app": "yyt1771-af-web-station", "version": "0.1.0"}
```

## Frontend Setup

Install frontend dependencies:

```bash
npm --prefix frontend install
```

Start the frontend development server:

```bash
npm --prefix frontend run dev
```

Build and check the frontend:

```bash
npm --prefix frontend run build
npm --prefix frontend run test
npm --prefix frontend run lint
```

## Root Scripts

The root `package.json` exposes convenience commands:

```bash
npm run backend:test
npm run backend:lint
npm run backend:format:check
npm run frontend:dev
npm run frontend:build
npm run frontend:test
npm run frontend:lint
npm run test
npm run lint
```

## Project Rules

- Do not reference or copy old project code.
- Keep formal ROI, A/B points, and `distance_px` in `acquisition` coordinates.
- Frontend must not compute formal A/B points or formal distance.
- Real camera SDK imports must stay isolated behind lazy-loaded adapters.
- Raw data and machine-specific config files must not be edited in place.
