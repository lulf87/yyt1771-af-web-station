# Existing Project Temperature Controller Integration Guide

This guide is for an already-created project that has completed the scaffold, detector, setup flow, run service, analysis, and export stages, but has not yet implemented the real Hik MVS camera adapter.

Do not restart the project and do not overwrite existing source files with the v3 starter pack. Treat this as an incremental feature stage.

## Goal

Add real temperature-controller support before implementing the real camera adapter.

The project must support:

- serial temperature-controller connection
- current temperature display
- target temperature setting
- power setting
- output enable/disable
- temperature status stored with run samples
- mock and offline operation without hardware

## Required architectural change

If the current project already has a read-only temperature source, keep it but refine the concepts:

```text
TemperatureSource
  Read-only provider of temperature readings.
  Examples: mock ramp source, file/CSV replay source.

TemperatureController
  Device-like controller that can read current temperature and may also set target temperature, set power, and enable/disable output.
  Examples: mock controller, serial ASCII controller, future Modbus controller.
```

Do not remove the existing mock/file temperature capability. Instead, wrap or adapt it into the new interface where appropriate.

## New backend package recommendation

Add a temperature package:

```text
backend/src/yyt1771_af/temperature/
  __init__.py
  base.py
  mock.py
  file_source.py
  serial_ascii.py
```

Add a service:

```text
backend/src/yyt1771_af/services/temperature_service.py
```

Add an API router:

```text
backend/src/yyt1771_af/api/temperature.py
```

Register the router in the FastAPI app.

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

Add a temperature panel, for example:

```text
frontend/src/components/TemperaturePanel.tsx
```

The panel should support:

- connection status
- current temperature display
- target temperature input
- power percent input
- output enable/disable
- error/status message display

## Run sample integration

Every run sample should continue to store the detection result and should also include temperature status.

Recommended sample shape:

```json
{
  "run_id": "...",
  "sample_index": 0,
  "timestamp_ms": 123456789,
  "temperature": {
    "timestamp_ms": 123456780,
    "temperature_c": 37.2,
    "status": "ok",
    "source_type": "serial_ascii"
  },
  "temperature_c": 37.2,
  "detection": { }
}
```

If temperature is unavailable, do not invent a value. Save the status:

```json
{
  "temperature": {
    "timestamp_ms": 123456780,
    "temperature_c": null,
    "status": "not_connected",
    "source_type": "serial_ascii"
  },
  "temperature_c": null
}
```

## Serial protocol rule

Do not hard-code serial commands unless the actual controller protocol is provided.

If the protocol is unknown, implement the serial adapter boundary and return `unsupported_protocol` for operations that cannot be executed safely.

Real serial commands should come from local ignored config such as `configs/local/dev_lab.local.yaml`, not from committed files.

## Cross-platform rules

- Do not hard-code `COM3`.
- Do not hard-code `/dev/tty.*`.
- Do not open the serial port at import time.
- Do not require serial hardware for mock/offline runs.
- Use `pathlib.Path` for paths.
- Use config for port, baud rate, timeout, and command set.

## Stage ordering

After this integration stage passes tests, continue with the Hik MVS camera adapter stage.

Recommended order:

```text
1. Temperature controller integration
2. Temperature UI panel
3. Run sample temperature integration
4. Tests and review
5. Hik MVS camera adapter
```
