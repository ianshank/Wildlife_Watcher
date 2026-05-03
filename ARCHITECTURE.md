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
| Kiosk application | Python, PyQt5, SQLite, paho-mqtt | Subscribes to MQTT topics, persists observations, manages thumbnails, and renders the touch UI. Tested via pytest with 98.87% branch coverage. |
| Phase 2 firmware slice | PlatformIO native and hardware environments | Isolates reusable power-management and networking refactors before they move back into the main firmware tree. Includes **39 Unity native tests** covering class_names, PowerManager, PIR debounce, wake-source classification, and publish logic. |
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
| `net_mqtt_format.h` | Pure thumb-payload budget and frame-topic formatting helpers used by `net_mqtt.*` and covered by native Unity tests. |
| `sscma_io.*` | Grove Vision AI V2 polling and detection shaping. |
| `sscma_decode.h` | Pure detection-decode helpers (class-id mask, score→confidence, max-score tracking, thumb-publish gate) used by `main.cpp` and covered by native Unity tests. |
| `power_mgmt.*` | Always-on versus PIR/deep-sleep behavior. `PowerManager::begin()` classifies the boot wake source; `last_wake_source()` exposes it for logging and policy decisions. |
| `power_policy.h` | Pure sleep-decision policy, `WakeSource` enum (`kColdBoot`, `kPirExt0`, `kTimer`, `kUnknown`), and `classify_wake_source()` function used by `power_mgmt.*` and covered by native Unity tests without Arduino dependencies. |
| `pir_event.h` | `constexpr should_accept_pir_edge()` debounce helper using `uint32_t` subtraction for wrap-safe `micros()` comparison; zero Arduino dependencies. |
| `class_names.h` | Inline class-label lookup without Arduino dependency; provides `configured_class_name()`, `kClassNameCount`, `kClassNameFallbackBufferSize`. |
| `config.h`, `topic_names.h`, `fps_meter.h`, `debounce.h` | Shared constants and lightweight reusable helpers. |

Native test coverage includes **39 Unity tests** covering: class_names lookup, MQTT thumb-budget and topic-format helpers (null-arg, truncation, zero-budget edge cases), runtime config-constant exposure, PowerManager stubs + `last_wake_source()` accessor, pure sleep-decision policy, `classify_wake_source()` with all four enum variants, `should_accept_pir_edge()` (first edge, within debounce window, exact boundary, uint32 wraparound), PIR and wake-boot-grace config constants, and SSCMA detection-decode helpers. Tests use `power_mgr_stubs.cpp` to remain hardware-independent in the native environment.

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

## Operational Tooling — Live Validation Surface

Under `scripts/` the repo carries a Python operational-tooling layer that runs from the developer workstation against the deployed Pi + camera, complementing the in-repo unit, integration, and native firmware suites.

| Script | Responsibility |
| --- | --- |
| `_pi_creds.py` | Single source of truth for Pi SSH credentials (`PI_HOST`/`PI_USER`/`PI_PASS` env vars). All other scripts import it; no passwords live in source. |
| `verify_pi_live.py` | Pings the Pi, asserts mosquitto is listening, and watches `wildlife/status/+` for camera heartbeats. |
| `verify_pi_diagnose.py` / `verify_pi_deepdive.py` | Triage helpers: inspect mosquitto/kiosk/SSH state and pull recent journals when the live check is unhappy. |
| `verify_pi_roundtrip.py` | Synthetic publish + remote `sqlite3` read-back to prove the kiosk consumed and persisted a detection. |
| `verify_e2e_journey.py` | Four-stage live end-to-end validator: real camera heartbeat → synthetic-camera publish (detection + retained base64 thumbnail) → SSH-side row equality check on `observations.db` → byte-identity comparison of the stored `thumb_jpeg` BLOB. Exit 0 only on full pass. |
| `read_xiao_serial.py` | Timed USB-serial capture from the XIAO (port/baud/duration overridable via `XIAO_PORT`/`XIAO_BAUD`/`XIAO_READ_SECS`). |

This layer is intentionally outside the unit-test perimeter: it touches a real Pi over SSH and a real broker over MQTT, and it is the post-deploy gate that exercises the same publish path the camera takes (impersonating a node) so any kiosk-side parsing / persistence / thumbnail-attachment regression is caught before sign-off.

## Operational Constraints

- GitHub repository settings should be aligned so the default branch is `main`.
- PlatformIO validation depends on a local `platformio` installation, which is not currently available in this environment.
- Phase 3 remains an offline training and export path only; deployment still targets the Grove Vision AI V2 Ethos-U55 path and does not introduce a Jetson runtime tier.
- The mypy typecheck gate now covers **24 source files** (kiosk module, all tests, `scripts/`, `deploy.py`, and `.agents/harness/orchestrator.py`). Zero type errors are enforced via `warn_unused_ignores = true`.
