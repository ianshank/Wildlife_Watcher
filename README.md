# Wildlife Watcher - Phase 1

Wireless wildlife detection system using Grove Vision AI V2 + XIAO ESP32S3 Sense as
the camera node, and a Raspberry Pi Zero 2 W with a Waveshare 7" touchscreen as the
display/logging node. All communication over 2.4 GHz WiFi via MQTT.

## Architecture

```text
[Camera Node]                                [Display Node]
Grove Vision AI V2 --I2C-- XIAO ESP32S3 Sense
  |- camera                     | WiFi (2.4 GHz)
  |- Ethos-U55 NPU              | MQTT
  `- runs YOLO model            v
                          Pi Zero 2 W (Mosquitto broker)
                                   |
                                   `- Waveshare 7" touch display
                                      |- PyQt5 kiosk UI
                                      |- SQLite log
                                      `- Image archive
```

## Phase status

| Phase | Status | Scope |
| ----- | ------ | ----- |
| 1 | Complete | Pi kiosk, MQTT broker, SQLite storage, XIAO ESP32S3 firmware |
| 2 | In progress | PIR wake, deep sleep, power budget, reusable firmware modules |
| 3 | Planned | Dataset prep, YOLO export, TFLite int8 + Vela for the Grove Vision AI V2 Ethos-U55 |

## What's in this package

```text
wildlife-watcher-phase1/
|- AGENTS.md                         # repo-level agent guidance
|- .gitignore                        # local-only outputs, secrets, generated assets
|- ARCHITECTURE.md                   # C4-style reviewer architecture map
|- CHANGELOG.md                      # unreleased change summary
|- README.md                         # this file
|- pyproject.toml                    # lint, type, test, coverage config
|- requirements-dev.txt              # dev dependencies
|- .agents/
|  |- harness/
|  |  `- orchestrator.py             # repo-local command runner
|  `- skills/                        # reusable command-oriented skills
|- .github/
|  |- workflows/
|  |  `- ci.yml                      # Python + firmware CI
|  `- agents/                        # custom phase and quality agents
|- docs/
|  |- 01-pi-setup.md                 # Pi Zero 2 W base install
|  |- 02-grove-flashing.md           # Flash Grove Vision AI V2 via SenseCraft
|  |- 03-xiao-firmware.md            # Build & flash XIAO ESP32S3 Sense
|  |- 04-bring-up.md                 # End-to-end bring-up and smoke test
|  |- 05-troubleshooting.md          # Common gotchas
|  `- 06-regression-checklist.md     # reviewer-facing regression runbook
|- pi-display-node/
|  |- install.sh                     # one-shot installer for the Pi
|  |- mosquitto/
|  |  |- wildlife.conf               # Mosquitto broker config
|  |  `- passwd.example              # passwd file template
|  |- kiosk/
|  |  |- wildlife_kiosk.py           # PyQt5 touchscreen UI
|  |  |- requirements.txt
|  |  `- config.yaml                 # broker/UI settings
|  |- systemd/
|  |  |- wildlife-kiosk.service
|  |  `- wildlife-mosquitto.override.conf
|  |- schema/
|  |  `- observations.sql            # SQLite DDL
|  `- tests/                         # pytest suite for kiosk, MQTT, storage
|- camera-node-firmware/
|  |- platformio.ini                 # PlatformIO project for XIAO ESP32S3
|  |- src/
|  |  `- main.cpp                    # SSCMA -> MQTT bridge firmware
|  `- include/
|     `- secrets.h.example           # WiFi/MQTT credentials template
|- phase2/
|  `- camera-node-firmware/          # modular PIR/deep-sleep firmware scaffold
`- ml-pipeline/
   |- pyproject.toml                 # strict type/lint/test config for Phase 3
   |- src/wildlife_ml/               # dataset, export, eval, runtime helpers
   `- tests/                         # numpy/hypothesis coverage for export helpers
```

## Repository layout

- `wildlife-watcher-phase1/` is the stable Phase 1 baseline.
- `phase2/` is the Phase 2 worktree-equivalent area for PIR and deep-sleep firmware work.
- `ml-pipeline/` is the Phase 3 worktree-equivalent area for model prep, export, and validation.

This repo is now Git-backed on GitHub. The current phase-isolated slices still live as sibling directories inside the repo, and can stay there or move into dedicated `git worktree` checkouts later without changing the documented command surface.

## Reviewer handoff

Use these files as the fast path through the current repo state:

- `ARCHITECTURE.md` for the C4-style system, container, and component map.
- `CHANGELOG.md` for the current unreleased change summary.
- `docs/06-regression-checklist.md` for the pre-PR validation runbook.
- `AGENTS.md` for repo-level constraints and the stable command surface.

Use `main` as the base branch for new work until the stale `civ` default-branch metadata is corrected in GitHub repository settings.

## Bring-up order

1. **`docs/01-pi-setup.md`** - flash SD card, enable touchscreen, run `install.sh`,
   verify Mosquitto is listening on the LAN.
2. **`docs/02-grove-flashing.md`** - flash a SenseCraft pre-trained model onto the
   Grove Vision AI V2 (start with the COCO/Person Detection model, then move to
   Pet Detection or YOLO-World "bird" for actual wildlife use).
3. **`docs/03-xiao-firmware.md`** - fill in `secrets.h`, build with PlatformIO,
   flash to the XIAO ESP32S3 Sense.
4. **`docs/04-bring-up.md`** - physically connect XIAO to Grove, power on, watch
   detections flow into the kiosk UI.

## Quality gates

Run the standard checks through the repo harness so local runs and CI stay aligned.

```powershell
./setup_and_test.ps1
python .agents/harness/orchestrator.py quality
python .agents/harness/orchestrator.py lint
python .agents/harness/orchestrator.py typecheck
python .agents/harness/orchestrator.py test
python .agents/harness/orchestrator.py agents-md-coverage
python .agents/harness/orchestrator.py firmware-build
python .agents/harness/orchestrator.py firmware-build-phase2
python .agents/harness/orchestrator.py firmware-test-native
python .agents/harness/orchestrator.py ml-pipeline-lint
python .agents/harness/orchestrator.py ml-pipeline-typecheck
python .agents/harness/orchestrator.py ml-pipeline-test
python .agents/harness/orchestrator.py ml-pipeline-smoke
python .agents/harness/orchestrator.py mock-publish-detection --dry-run
```

PlatformIO-based commands require the `platformio` package to be installed in the active Python environment used to run these `python` commands. Run `agents-md-coverage` when `AGENTS.md` files move or expand.

## Agent harness

The repo-local harness keeps common workflows centralized:

- `.agents/harness/orchestrator.py` dispatches lint, typecheck, test, firmware build, ML pipeline validation, AGENTS coverage, and MQTT smoke publishing.
- `.agents/harness.toml` holds the reusable command and path configuration.
- `.agents/skills/run-quality-gates/` bundles the standard validation flow.
- `.agents/skills/mock-camera-node/` documents repeatable synthetic MQTT traffic.
- `.agents/skills/firmware-build-and-size/` scopes firmware build and size-check workflows.
- `.agents/skills/phase-worktree-bootstrap/` documents the phase-isolation layout used in this Git-backed workspace.
- `.github/agents/quality-gate.agent.md` scopes quality validation work.
- `.github/agents/kiosk-integration.agent.md` scopes Pi kiosk and MQTT bridge work.
- `.github/agents/firmware-build.agent.md` scopes PlatformIO build work.
- `.github/agents/phase2-pir.agent.md` scopes PIR, wake-on-motion, and deep-sleep work.
- `.github/agents/phase3-ml.agent.md` scopes model training and export work for the Ethos-U55 deployment path.

Use `AGENTS.md` files in each directory for local constraints before changing code in that subtree.

## MQTT topic structure

| Topic | QoS | Retained | Direction | Payload |
| --- | --- | --- | --- | --- |
| `wildlife/detections/<node_id>` | 1 | no | camera → display | JSON detection event |
| `wildlife/thumbs/<node_id>/<frame_id>` | 0 | yes | camera → display | base64 JPEG (≤16 KB) |
| `wildlife/status/<node_id>` | 1 | yes | camera → display | online/offline + IP |
| `wildlife/control/<node_id>` | 1 | no | display → camera | reserved (future use) |

### Detection event JSON

```json
{
  "ts": "2026-05-01T14:23:11Z",
  "node_id": "feeder-01",
  "frame_id": "f_018472",
  "detections": [
    {
      "class_id": 14,
      "class_name": "bird",
      "confidence": 0.87,
      "bbox": [142, 88, 310, 240]
    }
  ],
  "model": "coco_yolov8n",
  "fps": 10.4
}
```

## Hardware bill of materials (Phase 1)

| Item                                  | Qty | Notes                                            |
|---------------------------------------|----:|--------------------------------------------------|
| Grove Vision AI V2                    |   1 | already owned                                    |
| OV5647-62 camera for Grove            |   1 | order separately if not already in kit           |
| XIAO ESP32S3 Sense                    |   1 | already owned (acts as WiFi/MQTT bridge)         |
| Raspberry Pi Zero 2 W                 |   1 | already owned                                    |
| Waveshare 7" Touch Display Kit        |   1 | already owned                                    |
| 32 GB+ microSD card (A1/A2)           |   1 | for the Pi                                       |
| USB-C 5V/3A supply                    |   1 | for the camera node                              |
| 5V/3A supply for Waveshare kit        |   1 | per Waveshare spec                               |
| 2.4 GHz WiFi network                  |     | XIAO ESP32 only supports 2.4 GHz, not 5 GHz      |

## Next steps

- Phase 2: validate `phase2/camera-node-firmware/` native tests and hardware builds once PlatformIO is available, then continue PIR wake and power-budget work behind the modular interfaces.
- Phase 3: keep training and export off-device in `ml-pipeline/`, strengthen the typed export path, and feed validated payload fixtures back into kiosk regressions.
- Repo operations: keep the GitHub default branch aligned to `main`, rerun the same harness commands on each PR branch, and package follow-on slices behind the same shared CI and harness contract.
