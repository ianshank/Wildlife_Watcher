# Changelog

All notable changes to this workspace-ready repo slice are documented in this file.

## Unreleased

### Added

- Extended harness typecheck scope to include `pi-display-node/tests` (9 source files total: 5 kiosk sources + 4 test files).
- Created `phase2/camera-node-firmware/include/wildlife/class_names.h` abstraction layer for inline class-label lookup without Arduino dependency.
- Added 4 Unity firmware tests for class_names and PowerManager stubs (8 total native tests).
- Added `phase2/camera-node-firmware/include/wildlife/power_policy.h` so the Phase 2 sleep decision can be exercised in native tests without Arduino dependencies.
- Added 4 Unity firmware tests covering the PowerManager sleep-decision branches (12 total native tests).
- Added `phase2/camera-node-firmware/include/wildlife/net_mqtt_format.h` so the Phase 2 MQTT thumb budget and frame-topic formatting logic can be exercised in native tests without a `PubSubClient` stub.
- Added 4 Unity firmware tests covering MQTT thumb-budget and topic-format helpers (16 total native tests).
- Added `phase2/camera-node-firmware/include/wildlife/sscma_decode.h` with pure constexpr detection-decode helpers (class-id mask, score→confidence, max-score tracking, thumb-publish gate) used by `main.cpp::publish_frame` and covered by native Unity tests without SSCMA/Wire/Serial stubs.
- Added 5 Unity firmware tests covering SSCMA detection-decode helpers (21 total native tests).

### Changed

- Lifted previously hard-coded Phase 2 firmware tunables (serial baud, boot/poll/sleep-settle delays, detection/MQTT/WiFi buffer sizes, MQTT keepalive/socket-timeout/reconnect-backoff/QoS/will/topic-buffer sizes, WiFi connect timeout, model id) into overridable `WILDLIFE_*` macros + `kSerialBaud`, `kBootDelayMs`, `kPollIdleDelayMs`, `kDeepSleepSettleMs`, `kDetectionPayloadBytes`, `kFrameIdBufferBytes`, `kMqttBufferBytes`, `kMqttKeepAliveSeconds`, `kMqttSocketTimeoutSeconds`, `kMqttReconnectBackoffMs`, `kMqttStatusBufferBytes`, `kMqttWillBufferBytes`, `kMqttTopicBufferBytes`, `kMqttStatusQos`, `kWifiConnectTimeoutMs`, `kWifiPollIntervalMs`, `kModelId` constants in `phase2/camera-node-firmware/include/wildlife/config.h`, eliminating magic numbers from `main.cpp`, `net_mqtt.cpp`, `net_wifi.cpp`, and `power_mgmt.cpp`.
- Added 5 Unity firmware tests covering `format_thumb_topic` null guards, truncation reporting, zero-budget rejection, base64 quartet rounding, and runtime config-constant exposure (26 total native tests).
- Created `ml-pipeline/src/wildlife_ml/export/manifest.py` frozen dataclass linking ONNX models to class labels and kiosk metadata.
- Added 3 ExportManifest tests plus hypothesis property test for `prepare_image_batch` (14 total ml-pipeline tests).
- Exposed public helpers in class_names.h: `configured_class_name()`, `kClassNameCount`, `kClassNameFallbackBufferSize`.
- Created PowerManager stubs (`power_mgr_stubs.cpp`) for native test environment.
- Repo-local agent harness tasks for linting, type checking, testing, AGENTS coverage, firmware validation, and ML pipeline validation.
- Localized `AGENTS.md` guidance across the repo plus reusable agent-facing skills under `.agents/skills/`.
- Phase 2 firmware scaffold under `phase2/camera-node-firmware/` with reusable networking, power, and SSCMA module boundaries.
- Phase 3 `ml-pipeline/` scaffold for typed dataset preparation, export helpers, Vela parsing, and CPU-only smoke validation.
- Reviewer handoff docs: `ARCHITECTURE.md`, `docs/06-regression-checklist.md`, and this changelog.
- Root `.gitignore` for Python caches, PlatformIO output, secrets, SQLite runtime files, and generated ML assets.

### Changed

- Eliminated hard-coded values from firmware tests: topic roots, debounce timing, buffer sizes now derive from config constants.
- Refactored `phase2/camera-node-firmware/src/net_mqtt.cpp` to use pure helpers for base64 thumb-budget checks and frame-topic formatting before publishing.
- Strengthened ExportManifest API to accept dynamic `Sequence[str]` inputs, normalize to tuple, reject empty/blank class names.
- Fixed 9 mypy var-annotated errors in test files with explicit type annotations (`queue.Queue[object]`, `dict[int, Any]`).
- Updated `phase2/camera-node-firmware/src/sscma_io.cpp` to use `kClassNameFallbackBufferSize` constant.
- Raised the Python quality floor to an enforced 85% coverage threshold via the repo harness.
- Updated `README.md` to surface the harness command set, reviewer navigation, and non-Jetson next steps.
- Standardized workspace-level validation through `setup_and_test.ps1` delegating to `.agents/harness/orchestrator.py quality`.
- Aligned GitHub Actions with the repo harness by routing Python quality through the shared task surface and enforcing the same 85% coverage floor in CI.
- Added ML pipeline validation to GitHub Actions and updated repo docs to reflect the live Git-backed state and `main` branch base.
- Added a dedicated `ml-pipeline-lint` harness task so Ruff coverage for typed `numpy` code matches the documented CI and review surface.
- Normalized repository line-ending policy through `.gitattributes` and expanded `.gitignore` to keep local editor metadata out of the PR surface.

### Fixed

- Hardened kiosk regressions around MQTT lifecycle, UI edge flows, storage behavior, and thumbnail handling.
- Added editor-compatibility wrappers and stub headers for the original firmware tree and the Phase 2 firmware tree.
- Removed stale Jetson-oriented scope from project documentation and phase planning.
- Repaired the firmware SSCMA thumbnail and class-name integration for the current Seeed library contract in both the shipped and Phase 2 firmware paths.
- Restored PlatformIO native test discovery for the Phase 2 firmware suite and aligned embedded builds on the required C++17 mode.
