# Codex Prompt: Insert Temperature Controller Phase Into Existing Project

We have already implemented the new project up to the stage before the real Hik camera adapter. Do not restart the repository and do not overwrite existing code.

Your task is to add the missing real temperature controller control layer as a delta phase.

First read the current repository, especially:

- AGENTS.md
- docs/02_DETECTION_CONTRACT.md
- docs/03_ARCHITECTURE_TECH_ROUTE.md
- docs/05_API_CONTRACT.md
- docs/06_DATA_MODEL_CONTRACT.md
- docs/07_CROSS_PLATFORM_REQUIREMENTS.md
- docs/08_DEVELOPMENT_PLAN.md
- docs/09_TEST_PLAN.md
- docs/10_ACCEPTANCE_CHECKLIST.md
- current backend services, API routes, run sample model, export/report code, and frontend run/setup pages

Then produce an implementation plan before editing files.

## Goal

Add temperature controller support:

1. serial connection
2. current temperature display
3. target temperature setting
4. power percentage setting
5. output enable/disable
6. run sample temperature capture
7. temperature controller metadata in run/export/report

## Critical constraints

- Do not change A/B point definitions.
- Do not change BalloonEnvelopeDetector.
- Do not change WireStripDetector.
- Do not add a generic detector.
- Do not implement wire endpoint detection.
- Do not integrate the Hik camera yet.
- Do not require a real serial device for mock/offline tests.
- Do not open a serial port at Python import time.
- Do not hard-code COM ports or `/dev/tty.*`.
- Do not hard-code OS-specific paths.
- Do not put serial command strings directly inside API routes.
- Do not make the frontend pretend a serial command succeeded.

## Architecture

Add or adapt modules like:

```text
backend/src/yyt1771_af/temperature/base.py
backend/src/yyt1771_af/temperature/mock.py
backend/src/yyt1771_af/temperature/file_source.py
backend/src/yyt1771_af/temperature/serial_ascii.py
backend/src/yyt1771_af/services/temperature_service.py
backend/src/yyt1771_af/api/temperature.py
```

If the project already has a temperature source abstraction, extend it instead of creating an incompatible duplicate.

Use two roles:

```text
TemperatureSource
  read-only temperature provider for mock/offline runs

TemperatureController
  read/write controller for real lab operation
```

## Required model concepts

Add or align equivalent Pydantic models/enums:

```text
TemperatureControllerType:
  none
  mock
  file
  serial_ascii
  custom_serial

TemperatureControllerStatus:
  disconnected
  connecting
  connected
  error
  unsupported_protocol

TemperatureReadStatus:
  ok
  not_connected
  timeout
  parse_error
  unsupported
  error
```

Add models for:

```text
TemperatureReading
TemperatureControllerSnapshot
SetTargetTemperatureRequest
SetPowerRequest
SetOutputRequest
```

## Required backend interface

Implement a controller interface equivalent to:

```python
class TemperatureController:
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def snapshot(self) -> TemperatureControllerSnapshot: ...
    def read_current_temperature(self) -> TemperatureReading: ...
    def set_target_temperature(self, target_c: float) -> None: ...
    def set_power_percent(self, power_percent: float) -> None: ...
    def set_output_enabled(self, enabled: bool) -> None: ...
```

## Required adapters

Implement:

1. MockTemperatureController
   - supports connect/disconnect
   - returns current temperature
   - stores target temperature
   - stores power percent
   - stores output enabled
   - can simulate ramping

2. FileTemperatureSource
   - read-only temperature replay
   - if set_target_temperature or set_power_percent is called, return unsupported clearly

3. SerialAsciiTemperatureController
   - reads all serial config from profile/local config
   - command strings come from config
   - if commands are missing, return unsupported_protocol / unsupported operation
   - must not open serial at import time
   - must be safe when pyserial is not installed unless selected by profile

## Required API

Add these API routes:

```text
GET  /api/temperature/status
POST /api/temperature/connect
POST /api/temperature/disconnect
GET  /api/temperature/current
POST /api/temperature/target
POST /api/temperature/power
POST /api/temperature/output
```

API routes must call TemperatureService. Do not put serial protocol logic in routes.

## Required frontend

Add a TemperaturePanel to the relevant setup/run UI:

- shows connection status
- shows current temperature
- lets user connect/disconnect
- lets user set target temperature
- lets user set power percentage
- lets user enable/disable output
- shows API errors clearly

## Required run integration

If run samples already contain temperature fields, update them without breaking existing analysis.

Each sample should include:

```text
temperature_c
temperature_status
temperature_timestamp_ms
```

If temperature read fails, save status and continue the run if detection can still proceed.

## Required export/report update

Update CSV/JSON/XLSX exports to include:

```text
temperature_c
temperature_status
temperature_timestamp_ms
```

Add controller metadata to JSON/XLSX metadata where available:

```text
temperature_controller_type
target_temperature_c
power_percent
output_enabled
```

Do not leak local absolute paths.

## Required tests

Add or update tests for:

1. mock controller connect/disconnect
2. current temperature read
3. set target temperature
4. set power percent
5. set output enabled
6. invalid power rejected
7. file source rejects write operations as unsupported
8. serial adapter does not open at import time
9. missing serial command returns unsupported_protocol or unsupported
10. API status when disconnected
11. API set target when unsupported
12. run sample includes temperature status
13. export includes temperature fields
14. mock/offline tests pass without serial hardware

After implementation, run the relevant tests and report:

- files changed
- tests run
- tests passed/failed
- any remaining TODOs

Do not proceed to Hik camera integration in this task.
