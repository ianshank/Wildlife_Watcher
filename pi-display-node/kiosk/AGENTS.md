# Kiosk Agents

## Scope
`wildlife_kiosk.py` contains the full Phase 1 kiosk app: config loading, `MqttBridge`, `Storage`, `ThumbCache`, `WildlifeKiosk`, `ThumbTile`, and `DetailView`.

## Local Rules
- Keep MQTT ingress on the background thread and UI/state mutation on the Qt thread.
- Prefer queue-driven updates and small helper functions over direct cross-thread signal wiring.
- Preserve the public configuration surface in `config.yaml` and `test_config.yaml`.
- Add debug logging for branches that would be difficult to reproduce on a Pi Zero 2 W.

## Validation
- `python .agents/harness/orchestrator.py quality`
- `python .agents/harness/orchestrator.py mock-publish-detection --dry-run`
- `pytest pi-display-node/tests/test_kiosk_ui.py -v`