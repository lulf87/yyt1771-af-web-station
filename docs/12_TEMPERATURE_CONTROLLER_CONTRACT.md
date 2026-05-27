# 12 — Temperature Controller Contract

This file defines the real temperature-controller requirement. The project must support a hardware-free path first, but the architecture must also include a real serial controller path for lab use.

## Product requirement

The temperature controller is responsible for thermal process control and temperature telemetry during a run.

The UI and backend must support:

1. connecting to a configured controller,
2. disconnecting from the controller,
3. displaying current temperature,
4. setting target temperature,
5. setting power percentage or power limit,
6. enabling/disabling output when the hardware supports it,
7. saving temperature readings or temperature failure status with each run sample.

## Important distinction

There are two related concepts:

```text
TemperatureSource
  Read-only source of timestamped temperature values.
  Examples: mock ramp, offline CSV/JSONL.

TemperatureController
  Read/write hardware-facing controller.
  Examples: serial temperature controller with current temperature, target temperature, power setting, and output state.
```

A real serial temperature controller is both a source and a controller.

## Required interface

Implement a backend interface equivalent to:

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

The mock implementation should support every method.

The file implementation may be read-only and should return explicit unsupported status for set operations.

The serial implementation must map these methods to a real configured protocol.

## Serial adapter rules

The serial adapter must not assume a specific device protocol unless configured.

Rules:

- Do not hard-code serial ports.
- Do not hard-code command strings in API routes.
- Do not open serial ports at package import time.
- Do not require pyserial for mock/offline operation.
- Load pyserial only inside the serial adapter or optional dependency boundary.
- Serial port, baud rate, parity, stop bits, timeout, protocol name, command templates, and parsing rules must come from profile/local config.
- Unsupported protocol commands must return explicit failure status.
- Do not silently substitute mock temperature for a real serial controller failure.

## Configuration model

Example mock configuration:

```yaml
temperature_controller:
  type: mock
  enabled: true
  initial_temperature_c: 20.0
  ramp_rate_c_per_min: 2.0
  allow_set_target: true
  allow_set_power: true
  initial_target_temperature_c: 45.0
  initial_power_percent: 0.0
  output_enabled: false
```

Example offline file configuration:

```yaml
temperature_controller:
  type: file
  enabled: true
  temperature_file: ./sample_data/temperature_trace.csv
  loop: false
```

Example serial configuration. This is only a placeholder. Real commands belong in ignored local config after the actual controller protocol is known.

```yaml
temperature_controller:
  type: serial_ascii
  enabled: true
  port: REPLACE_WITH_LOCAL_SERIAL_PORT
  baud_rate: 9600
  bytesize: 8
  parity: N
  stopbits: 1
  timeout_s: 1.0
  write_timeout_s: 1.0
  poll_interval_s: 0.5
  protocol: configured_ascii
  command_set:
    read_current_temperature: null
    read_target_temperature: null
    set_target_temperature: null
    read_power_percent: null
    set_power_percent: null
    set_output_enabled: null
  parsing:
    temperature_regex: null
    power_regex: null
```

## API behavior

The API exposes temperature control through service methods, not serial code.

Required endpoints:

```text
GET  /api/temperature/status
POST /api/temperature/connect
POST /api/temperature/disconnect
GET  /api/temperature/current
POST /api/temperature/target
POST /api/temperature/power
POST /api/temperature/output
```

## UI behavior

The UI must include a temperature panel, either on the setup/run page or as a shared component.

The panel must show:

- connection state,
- controller type,
- current temperature,
- target temperature,
- power percentage,
- output enabled state,
- last error/status message.

The panel must allow:

- connect/disconnect,
- set target temperature,
- set power percentage,
- enable/disable output when supported.

## Run integration

Each run sample must include temperature data when available.

If a temperature read fails, the sample must not crash the run and must not fake a valid reading. Instead it should include explicit temperature status.

Example:

```json
{
  "run_id": "run_001",
  "sample_index": 42,
  "timestamp_ms": 123456789,
  "temperature": {
    "timestamp_ms": 123456780,
    "temperature_c": 37.2,
    "status": "ok",
    "message": null
  },
  "temperature_c": 37.2,
  "detection": {
    "status": "ok",
    "distance_px": 785.1
  }
}
```

## Safety and correctness rules

- Output must default to disabled unless the selected mock/real profile explicitly restores another state.
- Setting target temperature and setting power must validate numeric ranges.
- Power is represented as 0 to 100 percent at the API boundary.
- The exact meaning of power is adapter-specific and must be documented for the real controller.
- On disconnect or communication error, the controller state must be explicit.
- A failed temperature controller must not change the vision A/B detection contract.
