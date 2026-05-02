# Pi Display Node Agents

## Scope
This directory owns the Raspberry Pi runtime: kiosk UI, installer, MQTT broker config, SQLite schema, and the readiness unit.

## Key Files
- `install.sh`: one-shot installer and runtime bootstrap for the Pi.
- `kiosk/wildlife_kiosk.py`: PyQt5 application, MQTT bridge, storage layer, and detail view.
- `schema/observations.sql`: SQLite DDL for observations and node state.
- `mosquitto/wildlife.conf`: broker authentication, persistence, and message-size policy.
- `systemd/wildlife-kiosk.service`: readiness unit that ensures Mosquitto is active before the kiosk autostarts.

## Rules
- Keep runtime paths consistent with the installer (`/opt/wildlife`, `/etc/wildlife`, `/var/lib/wildlife`).
- Do not block the UI thread in kiosk code.
- Installer changes should preserve idempotence and be safe on already-initialized Pi nodes.

## Recommended Agents And Skills
- `kiosk-integration.agent.md` for UI, MQTT, and storage changes.
- `quality-gate.agent.md` after any Python edit.
- `.agents/skills/mock-camera-node/` when validating kiosk ingestion without hardware.