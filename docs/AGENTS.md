# Docs Agents

## Scope
The `docs/` directory is the operational runbook for building, flashing, installing, bringing up, and troubleshooting the wildlife watcher hardware.

## Local Rules
- Keep the bring-up order aligned with actual installer, firmware, and hardware behavior.
- When code changes user-facing setup steps, update the matching numbered document instead of adding disconnected notes elsewhere.
- Preserve phase boundaries: Phase 1 current runtime, Phase 2 PIR/power, Phase 3 off-device training with deployment back to the Grove Vision AI V2 path.