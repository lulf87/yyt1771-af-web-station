# Prompt: Integrate Temperature Controller into Existing Project

You are working inside an existing project that has already implemented the earlier starter-pack phases. Do not restart the project. Do not overwrite existing architecture. Add this as an incremental feature before implementing the real Hik MVS camera adapter.

Read first:

- AGENTS.md
- docs/01_PRODUCT_REQUIREMENTS.md
- docs/02_DETECTION_CONTRACT.md
- docs/03_ARCHITECTURE_TECH_ROUTE.md
- docs/05_API_CONTRACT.md
- docs/06_DATA_MODEL_CONTRACT.md
- docs/07_CROSS_PLATFORM_REQUIREMENTS.md
- docs/10_ACCEPTANCE_CHECKLIST.md
- docs/12_TEMPERATURE_CONTROLLER_CONTRACT.md
- docs/13_EXISTING_PROJECT_TEMPERATURE_INTEGRATION_GUIDE.md

Then inspect the current codebase and produce a short gap analysis:

1. What temperature-related code already exists?
2. Is it only read-only TemperatureSource, or does it already control a device?
3. Which models need to be extended?
4. Which API routers need to be added or changed?
5. Which frontend components need to be added or changed?
6. Which tests need to be added?

After the gap analysis, implement the smallest safe change set.

## Backend requirements

Add or update:

```text
backend/src/yyt1771_af/temperature/base.py
backend/src/yyt1771_af/temperature/mock.py
backend/src/yyt1771_af/temperature/file_source.py
backend/src/yyt1771_af/temperature/serial_ascii.py
backend/src/yyt1771_af/services/temperature_service.py
backend/src/yyt1771_af/api/temperature.py
```

Names may be adapted to the existing package layout, but the layering must remain the same.

Implement:

- TemperatureController interface
- TemperatureSource interface if not already present
- TemperatureReading model
- TemperatureControllerSnapshot model
- MockTemperatureController
- FileTemperatureSource or equivalent read-only replay source
- SerialAsciiTemperatureController boundary
- TemperatureService
- `/api/temperature/*` endpoints

## Required API

```text
GET  /api/temperature/status
POST /api/temperature/connect
POST /api/temperature/disconnect
GET  /api/temperature/current
POST /api/temperature/target
POST /api/temperature/power
POST /api/temperature/output
```

## Frontend requirements

Add a TemperaturePanel or equivalent UI component that displays:

- connection status
- current temperature
- target temperature
- power percent
- output enabled/disabled
- status/error messages

It must allow:

- connect
- disconnect
- set target temperature
- set power percent
- enable/disable output

## Run service integration

If the project already has RunService, update it so every sample can include temperature reading data.

Rules:

- If temperature read succeeds, save `temperature_c`.
- If temperature read fails or device is disconnected, save status and null temperature.
- Do not crash the run because temperature is temporarily unavailable unless the selected profile explicitly requires temperature.
- Do not fake temperature values.

## Serial adapter safety rules

- Do not open serial ports at import time.
- Do not hard-code COM ports.
- Do not hard-code `/dev/tty.*`.
- Do not hard-code real protocol commands unless provided in config.
- If protocol commands are missing, return `unsupported_protocol`.
- The app must still run in mock/offline mode without serial hardware.

## Tests required

Add tests for:

1. Mock controller connect/disconnect.
2. Mock current temperature read.
3. Mock target temperature setting.
4. Mock power setting.
5. Invalid power percent rejection.
6. File temperature replay if file source exists.
7. Serial adapter construction without opening a port.
8. Missing command set returns unsupported protocol.
9. API status when disconnected.
10. API target/power/output handling.
11. Run samples include temperature status.
12. Mock/offline tests still pass without real serial hardware.

## Do not do yet

- Do not implement real Hik MVS camera adapter in this task.
- Do not copy from or inspect any old project.
- Do not change A/B point definitions.
- Do not change BalloonEnvelopeDetector or WireStripDetector semantics.
- Do not make frontend calculate official A/B or Af.
- Do not require real temperature hardware for tests.

After implementation, run the relevant backend and frontend tests and summarize results.
