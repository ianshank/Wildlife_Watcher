---
name: mock-camera-node
description: "Publish synthetic Wildlife Watcher detection payloads to the configured MQTT broker. Use for kiosk smoke tests, UI validation, MQTT topic checks, and display-node debugging without hardware."
argument-hint: "Provide node ID, class name, count, or dry-run options if needed."
user-invocable: true
---

# Mock Camera Node

## When To Use
- Validate the kiosk feed without a real XIAO or Grove Vision AI V2.
- Confirm MQTT topic routing and detection payload parsing.
- Reproduce display-node issues using controlled synthetic events.

## Procedure
1. Confirm the target `WILDLIFE_CONFIG` or `.agents/harness.toml` points to the correct broker.
2. Run `python .agents/harness/orchestrator.py mock-publish-detection --dry-run` to inspect the payload.
3. Remove `--dry-run` to publish one or more events.
4. Validate with `pi-display-node/tests/` or a live kiosk session.