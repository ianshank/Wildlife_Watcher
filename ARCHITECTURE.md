# Architecture

This document gives a C4-style view of the Wildlife Watcher application as it exists in this workspace. It is intended for reviewers who need a fast map of the runtime path, the phase-isolated development areas, and the configuration boundaries that keep the system reusable and backward-compatible.

## System Context

The deployed system captures detections on a Grove Vision AI V2 camera stack, forwards those events over WiFi and MQTT, and presents the resulting activity feed on a Raspberry Pi kiosk.

| Actor or system | Role |
| --- | --- |
| Field operator | Powers and maintains the camera node, Pi kiosk, and local network. |
| Wildlife camera node | Collects Grove Vision AI V2 detections and publishes status, detections, and thumbnails. |
| MQTT broker on the Pi | Carries the event contract between the camera node and the kiosk. |
| Pi kiosk UI | Displays recent detections, stores observations, and renders image details. |
| Offline training workstation | Produces future model exports for the Grove Vision AI V2 deployment path. |

## Container View

| Container | Technology | Responsibility |
| --- | --- | --- |
| Camera node firmware | PlatformIO, Arduino, XIAO ESP32S3 Sense | Bridges SSCMA detections from the Grove Vision AI V2 into MQTT topics and publishes node status. |
| Display node broker | Mosquitto on Raspberry Pi Zero 2 W | Provides the local MQTT transport and retained status channel. |
| Kiosk application | Python, PyQt5, SQLite, paho-mqtt | Subscribes to MQTT topics, persists observations, manages thumbnails, and renders the touch UI. Tested via pytest with 98.85% branch coverage. |
| Phase 2 firmware slice | PlatformIO native and hardware environments | Isolates reusable power-management and networking refactors before they move back into the main firmware tree. Includes 8 Unity native tests for class_names, PowerManager stubs, and publish logic. |
| Phase 3 ML pipeline | Python, numpy, pytest, mypy | Validates dataset prep, export helpers (including ExportManifest dataclass), Vela parsing, and smoke checks for the Ethos-U55 deployment path. Includes 14 tests with hypothesis property testing. |

## Component View — Display Node

The current Phase 1 kiosk runtime is centered in `pi-display-node/kiosk/wildlife_kiosk.py`.

| Component | Responsibility |
| --- | --- |
| `load_config()` | Loads broker, UI, and storage settings from YAML instead of hard-coded values. |
| `MqttBridge` | Connects to Mosquitto, translates inbound topic payloads into typed application events, and manages online or offline state. |
| `Storage` | Owns SQLite persistence for observations, thumbnails, and node state. |
| `ThumbCache` | Prevents repeated image decoding and keeps the recent-view rendering path lightweight. |
| `WildlifeKiosk` | Coordinates feed refresh, detail rendering, and the top-level Qt application lifecycle. |

Supporting files under `pi-display-node/` define the broker configuration, the schema, the installer, and the systemd units that keep the kiosk process stable on the Pi.

## Component View — Camera Node

There are two firmware surfaces in this workspace because Phase 2 is being isolated from the shipped Phase 1 baseline.

### Phase 1 firmware baseline

`camera-node-firmware/src/main.cpp` is the production composition root for the current deployment. It is responsible for:

- reading credentials from `include/secrets.h`
- polling the Grove Vision AI V2 through SSCMA
- serializing detection payloads
- publishing status, detections, and thumbnails over MQTT

Compatibility headers under `camera-node-firmware/include/wildlife/compat/` keep editor diagnostics stable outside full PlatformIO builds.

### Phase 2 modular firmware slice

`phase2/camera-node-firmware/` breaks the firmware into narrower modules so PIR wake and power-management work can land without reopening the whole main loop.

| Module | Responsibility |
| --- | --- |
| `net_wifi.*` | WiFi connection ownership and reconnection policy. |
| `net_mqtt.*` | Topic formatting and publish lifecycle. |
| `sscma_io.*` | Grove Vision AI V2 polling and detection shaping. |
| `power_mgmt.*` | Always-on versus PIR/deep-sleep behavior. |
| `class_names.h` | Inline class-label lookup without Arduino dependency; provides `configured_class_name()`, `kClassNameCount`, `kClassNameFallbackBufferSize`. |
| `config.h`, `topic_names.h`, `fps_meter.h`, `debounce.h` | Shared constants and lightweight reusable helpers. |

Native test coverage includes 8 Unity tests covering class_names lookup, PowerManager stubs, and core publish logic. Tests use `power_mgr_stubs.cpp` to enable testing in native environment without hardware dependencies.

The Phase 2 tree is treated as worktree-equivalent isolation. The repo is now Git-backed, but the existing in-repo phase layout remains the active roadmap surface.

## Component View — ML Pipeline

The Phase 3 ML pipeline under `ml-pipeline/src/wildlife_ml/` provides typed helpers for dataset preparation, model export, and validation.

| Component | Responsibility |
| --- | --- |
| `data.*` | CUB-200-2011 dataset loading, preprocessing, and augmentation helpers. |
| `export.manifest` | `ExportManifest` frozen dataclass linking ONNX models to class labels and kiosk metadata. Provides `from_config()`, `to_dict()`, `to_summary()` with dynamic input normalization. |
| `export.onnx` | ONNX export helpers including `prepare_image_batch` for input preprocessing. |
| `export.tflite` | TFLite conversion helpers for Ethos-U55 deployment path. |
| `export.vela` | Vela report parsing for Ethos-U55 performance analysis. |
| `runtime.onnx_smoke` | CPU-only ONNX smoke validation without Jetson dependencies. |

Test coverage includes 14 tests with hypothesis property testing for shape/dtype invariants and ExportManifest validation (round-trip, normalization, blank-label rejection).

## Data and Configuration Boundaries

Configuration and contracts are intentionally kept out of ad hoc source edits.

- `pi-display-node/kiosk/config.yaml` owns kiosk broker, UI, and storage configuration.
- `.agents/harness.toml` owns the local validation command inventory and Python path configuration.
- `camera-node-firmware/include/secrets.h.example` and `phase2/camera-node-firmware/include/secrets.h.example` define the credential template for local firmware builds.
- MQTT topic conventions are documented in `README.md` and enforced through the firmware and kiosk integration path.

This keeps the runtime configurable while preserving stable command names and message shapes across phases.

## Phase Isolation Strategy

This workspace currently keeps phase isolation in-repo even though Git worktrees are now available.

- `wildlife-watcher-phase1/` is the shipped Phase 1 baseline.
- `wildlife-watcher-phase1/phase2/` holds firmware refactors and power-management work.
- `wildlife-watcher-phase1/ml-pipeline/` holds offline training and export tooling.

That separation allows Phase 2 and Phase 3 work to evolve without destabilizing the deployed kiosk and firmware path.

## Operational Constraints

- GitHub repository settings should be aligned so the default branch is `main`; stale `civ` metadata will confuse compare flows, protection rules, and review defaults.
- PlatformIO validation depends on a local `platformio` installation, which is not currently available in this environment.
- Phase 3 remains an offline training and export path only; deployment still targets the Grove Vision AI V2 Ethos-U55 path and does not introduce a Jetson runtime tier.
