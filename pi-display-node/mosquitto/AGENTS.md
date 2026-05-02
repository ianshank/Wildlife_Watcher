# Mosquitto Config Agents

## Scope
This directory owns the broker-side MQTT configuration used by the display node.

## Local Rules
- Preserve authenticated access and retained-message persistence.
- Keep `message_size_limit` aligned with thumbnail payload expectations.
- Any broker-side topic or auth change must stay compatible with the kiosk config and firmware topics.