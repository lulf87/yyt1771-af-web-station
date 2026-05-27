# Temperature Controller Integration Guide

Use this guide when the new project has already completed the scaffold, vision detectors, setup flow, run service, AF analysis, and export/report phases, but has not yet integrated the real Hik camera adapter.

Do not restart the project. Do not overwrite the current repository with a newer starter pack. Treat this as a delta phase to insert before the Hik camera adapter phase.

## Goal

Add real temperature controller support to the current project:

- serial connection
- connection/disconnection status
- current temperature display
- target temperature setting
- power percentage setting
- output enable/disable
- run sample temperature capture
- export/report preservation of temperature and controller metadata

The implementation must preserve all existing detector, setup, run, analysis, and export behavior.

## Required design

Add a temperature controller boundary separate from camera and vision.

Suggested backend modules:

```text
backend/src/yyt1771_af/temperature/
  __init__.py
  base.py
  mock.py
  file_source.py
  serial_ascii.py

backend/src/yyt1771_af/services/
  temperature_service.py

backend/src/yyt1771_af/api/
  temperature.py
```

If the current project already has a temperature source interface, keep it and extend it. Do not duplicate incompatible temperature abstractions.

Use these concepts:

```text
TemperatureSource
  Read-only source used by mock/offline runs.

TemperatureController
  Read/write temperature device used by lab operation.
```

A serial temperature controller must not open a serial port at import time. It may only connect when the user calls the connect API or when the selected profile explicitly enables auto-connect.

## API to add

```text
GET  /api/temperature/status
POST /api/temperature/connect
POST /api/temperature/disconnect
GET  /api/temperature/current
POST /api/temperature/target
POST /api/temperature/power
POST /api/temperature/output
```

## Frontend to add

Add a TemperaturePanel to the setup/run UI:

- connection state
- current temperature
- target temperature input
- power percentage input
- output enable/disable
- error/status display

The panel must call backend API only. It must not simulate a successful serial write in the frontend.

## Run integration

If run samples already contain `temperature_c`, keep that field.

During a run, each sample should include:

```text
temperature_c
temperature_status
temperature_timestamp_ms
```

If the temperature read fails, do not invent a temperature. Save the failure status.

## Analysis/export integration

Do not rewrite AF analysis. It should continue using `temperature_c` and `distance_px`.

Update exports to include temperature controller metadata where available:

```text
temperature_controller_type
serial_port or masked/local identifier if appropriate
target_temperature_c
power_percent
output_enabled
```

Do not leak absolute SDK paths or private local paths in exported reports.

## Cross-platform rules

- Use pathlib.Path.
- Do not hard-code COM3, /dev/tty.*, /tmp, /Users, or C:\ paths.
- Serial port must come from config or API request.
- Do not use shell-specific commands.
- Mock/offline modes must run without any serial device attached.
- Windows/macOS differences belong only in local config and hardware adapters.
