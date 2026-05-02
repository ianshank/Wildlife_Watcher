# Camera Firmware Agents

## Scope
This directory owns the PlatformIO project for the XIAO ESP32S3 Sense camera node. It connects WiFi, MQTT, and the Grove Vision AI V2 I2C interface.

## Key Files
- `platformio.ini`: board, framework, debug flags, library dependencies.
- `src/main.cpp`: current monolithic firmware entrypoint for status, detections, thumbnails, and heartbeat logic.
- `include/secrets.h.example`: credentials and node identity contract.

## Rules
- Keep build configuration in `platformio.ini` and secrets in `secrets.h`; do not embed broker values or credentials in `.cpp` files.
- Preserve topic compatibility with the Phase 1 MQTT contract.
- Prefer refactoring toward reusable modules (`wifi`, `mqtt_pub`, `power_mgmt`, `sscma_io`) without changing external payload shapes.

## Recommended Agents And Skills
- `firmware-build.agent.md` for compile and dependency validation.
- `phase2-pir.agent.md` for PIR/deep-sleep work that should live in a dedicated worktree.
- `.agents/skills/firmware-build-and-size/` for repeatable build invocations.