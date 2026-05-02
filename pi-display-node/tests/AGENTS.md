# Pi Test Agents

## Scope
This directory contains the Python regression suite for the kiosk, MQTT bridge, storage layer, thumbnail cache, and config loading.

## Local Rules
- Keep fast tests in-process and deterministic.
- Prefer fixtures in `conftest.py` over per-file test scaffolding.
- Add targeted tests for every new branch in `wildlife_kiosk.py`, especially queue handling, config validation, and storage edge cases.
- Run tests through the harness or `setup_and_test.ps1` so ruff, mypy, and coverage stay aligned.

## Useful Skills
- `.agents/skills/run-quality-gates/`
- `.agents/skills/mock-camera-node/`
- `.agents/skills/agents-md-coverage/`