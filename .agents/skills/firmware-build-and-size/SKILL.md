---
name: firmware-build-and-size
description: "Build the Wildlife Watcher camera-node firmware with PlatformIO and inspect the resulting compile output. Use for firmware compile checks, dependency issues, and binary-size review."
argument-hint: "Describe the firmware branch or worktree you want to validate."
user-invocable: true
---

# Firmware Build And Size

## When To Use
- Validate firmware edits before flashing hardware.
- Reproduce PlatformIO dependency or compiler failures.
- Review whether new features are growing the build unexpectedly.

## Procedure
1. Read `camera-node-firmware/AGENTS.md` for current constraints.
2. Run `python .agents/harness/orchestrator.py firmware-build`.
3. Inspect the PlatformIO summary for dependency, size, or linker regressions.
4. Keep payload contracts backward-compatible with the kiosk.