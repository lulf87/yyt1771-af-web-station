# Codex Prompt: Review Temperature Controller Integration

Review the temperature controller integration before continuing to Hik camera work.

Check all of the following:

1. The project still does not reference or copy any old project code.
2. BalloonEnvelopeDetector and WireStripDetector behavior is unchanged.
3. There is no generic detector.
4. wire_strip is not endpoint detection.
5. Mock/offline modes run without serial hardware.
6. Importing the backend does not open a serial port.
7. Importing the backend does not require pyserial unless the serial profile is selected.
8. Serial port, baud rate, commands, and protocol settings come from config/local config.
9. No COM port or /dev/tty.* is hard-coded.
10. API routes do not contain serial protocol details.
11. TemperatureService owns controller state.
12. Frontend TemperaturePanel displays real API state and errors.
13. Run samples include temperature_c, temperature_status, and temperature_timestamp_ms.
14. Failed temperature reads do not invent temperature values.
15. AF analysis still uses saved run samples and remains backend-owned.
16. CSV/JSON/XLSX exports include temperature fields.
17. Exported reports do not leak absolute local paths.
18. Tests cover mock, file, serial-missing/unsupported, API, run sample, and export paths.
19. macOS and Windows compatibility rules are preserved.
20. The project is still ready for the next phase: isolated Hik MVS camera adapter.

If any item fails, fix it before continuing.
