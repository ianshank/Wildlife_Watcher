# Firmware Source Agents

## Scope
`main.cpp` currently owns WiFi connection, MQTT session setup, status publishing, detection parsing, debounce logic, and thumbnail publishing.

## Local Rules
- Treat `main.cpp` as the behavioral source of truth until the code is split into smaller translation units.
- Keep publish payloads backward-compatible with the kiosk parser.
- Add logging on the serial console for new branches that would otherwise be hard to debug on-device.
- Any change to debounce, heartbeat, or payload shape should be paired with a host-runnable test or a documented validation step.