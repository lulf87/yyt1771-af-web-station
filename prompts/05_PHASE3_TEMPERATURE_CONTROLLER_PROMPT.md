# Prompt 05 — Temperature Controller Integration

Read these files first:

- `AGENTS.md`
- `docs/03_ARCHITECTURE_TECH_ROUTE.md`
- `docs/05_API_CONTRACT.md`
- `docs/06_DATA_MODEL_CONTRACT.md`
- `docs/07_CROSS_PLATFORM_REQUIREMENTS.md`
- `docs/12_TEMPERATURE_CONTROLLER_CONTRACT.md`

Goal: add temperature-controller support without breaking mock/offline development.

Before coding, produce a concise implementation plan.

## Required backend work

Implement or update:

1. `temperature/base.py`
   - `TemperatureController` interface
   - controller snapshot model usage
   - reading/status semantics

2. `temperature/mock.py`
   - mock current temperature
   - target temperature state
   - power percentage state
   - output enabled state
   - connect/disconnect

3. `temperature/file_source.py`
   - read timestamped temperature data from CSV or JSONL
   - read-only controller behavior
   - explicit unsupported status for target/power/output commands

4. `temperature/serial_ascii.py`
   - adapter skeleton or implementation driven by config
   - no port opens at import time
   - no hard-coded ports or commands
   - optional pyserial import only inside adapter code
   - explicit unsupported status if command set is missing

5. `services/temperature_service.py`
   - connect/disconnect
   - status snapshot
   - read current temperature
   - set target temperature
   - set power percent
   - set output enabled

6. `api/temperature.py`
   - `GET /api/temperature/status`
   - `POST /api/temperature/connect`
   - `POST /api/temperature/disconnect`
   - `GET /api/temperature/current`
   - `POST /api/temperature/target`
   - `POST /api/temperature/power`
   - `POST /api/temperature/output`

7. Run integration
   - include `TemperatureReading` or explicit temperature status in run samples when run service exists
   - do not crash a run when temperature reading fails
   - do not fake valid readings for real controller failures

## Required frontend work

Add a temperature panel that can:

- show connection state
- show current temperature
- show target temperature
- show power percent
- show output enabled state
- connect/disconnect
- set target temperature
- set power percent
- enable/disable output when supported
- show last error/status message

The frontend must call backend API only. It must not speak serial protocol.

## Tests

Add tests for:

- mock temperature controller connect/disconnect
- mock current temperature read
- setting target temperature
- setting power percent
- rejecting invalid power percent
- file temperature source read behavior
- serial config validation
- serial adapter does not open a port at import time
- API returns explicit not-connected/unsupported statuses

## Constraints

- No real serial port is required for tests.
- Do not hard-code `COM3`, `/dev/tty.*`, `/dev/cu.*`, or local paths.
- Do not add OS-specific shell commands.
- Do not change the vision A/B detection contract.
- Do not add a third public detector.
- Do not make mock/offline mode depend on pyserial.

After implementation, run relevant tests and summarize results.
