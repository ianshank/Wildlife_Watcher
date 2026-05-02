# Systemd Agents

## Scope
This directory contains the readiness unit that gates kiosk startup on broker availability.

## Local Rules
- This unit is not the kiosk process itself; it is a readiness check for Mosquitto before the user's X session starts.
- Keep user-substituted values template-safe and installer-friendly.
- Changes here should be validated against `install.sh` so the deployment flow remains consistent.