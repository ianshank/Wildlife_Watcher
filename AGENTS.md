# Wildlife Watcher Agent Guide

## Repo Map
- `camera-node-firmware/`: XIAO ESP32S3 Sense firmware that bridges Grove Vision AI V2 detections to MQTT.
- `pi-display-node/`: Raspberry Pi kiosk, installer, SQLite schema, Mosquitto config, and systemd readiness unit.
- `docs/`: bring-up and troubleshooting flow for the physical deployment.
- `.agents/`: reusable harness and skills for repo-local automation.
- `.github/agents/`: custom subagents for quality gates, kiosk integration, firmware builds, and roadmap phases.

## Global Rules
- Run repo quality gates through `.agents/harness/orchestrator.py` or `setup_and_test.ps1`; do not invent ad hoc commands.
- Keep broker hosts, paths, credentials, and topic shapes in `config.yaml`, `.agents/harness.toml`, `platformio.ini`, or `secrets.h.example`; do not hard-code new values in source.
- Never commit secrets or generated firmware/build artifacts.
- Prefer backward-compatible refactors and additive changes. If a behavior moves, leave stable command surfaces and config keys intact.
- For Python changes, keep PyQt work on the UI thread and push network ingress through the queue-based bridge.

## Standard Commands
- Full quality gate: `python .agents/harness/orchestrator.py quality`
- Mock MQTT publisher: `python .agents/harness/orchestrator.py mock-publish-detection --dry-run`
- AGENTS coverage check: `python .agents/harness/orchestrator.py agents-md-coverage`
- Firmware build: `python .agents/harness/orchestrator.py firmware-build`
- Phase 2 firmware build: `python .agents/harness/orchestrator.py firmware-build-phase2`
- Phase 2 native tests: `python .agents/harness/orchestrator.py firmware-test-native`
- Phase 3 type check: `python .agents/harness/orchestrator.py ml-pipeline-typecheck`
- Phase 3 tests: `python .agents/harness/orchestrator.py ml-pipeline-test`
- Phase 3 smoke summary: `python .agents/harness/orchestrator.py ml-pipeline-smoke`

## Worktree Strategy
- Keep roadmap work isolated from the Phase 1 baseline.
- In this workspace, Phase 2 lives under `phase2/` and Phase 3 lives under `ml-pipeline/` because the repo is not currently backed by `.git`.
- If the repo is later initialized as Git, those directories can be moved into dedicated `git worktree` checkouts without changing the command surfaces.
- Do not mix phase-specific experiments back into shared paths until the harness quality gate is green.

## Agent Surface
- Use `quality-gate.agent.md` for ruff, mypy, pytest, coverage, and pre-commit style validation.
- Use `kiosk-integration.agent.md` for UI, MQTT, and SQLite flows in `pi-display-node/`.
- Use `firmware-build.agent.md` for PlatformIO build work.
- Use `phase2-pir.agent.md` and `phase3-ml.agent.md` when work is explicitly phase-scoped and should stay in `phase2/` or `ml-pipeline/`.
- Use `.agents/skills/run-quality-gates/` and `.agents/skills/mock-camera-node/` for repeatable command-driven workflows.