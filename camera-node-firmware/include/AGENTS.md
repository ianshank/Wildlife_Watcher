# Firmware Include Agents

## Scope
This directory holds public headers for the firmware project. Today it only includes `secrets.h.example`, but future refactors should move shared interfaces here.

## Rules
- Keep this directory free of committed secrets.
- If new headers are added, treat them as stable contracts between firmware modules.
- Default values belong in `platformio.ini` or runtime config, not in headers that will drift across environments.