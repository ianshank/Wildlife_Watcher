# Changelog

All notable changes to this workspace-ready repo slice are documented in this file.

## [Unreleased] — Phase 2 hardware wiring & ops hardening

### Added

- **`phase2/camera-node-firmware/src/main.cpp`** — `IRAM_ATTR pir_isr()` interrupt handler with namespace-scope `volatile` state (`g_last_pir_micros`, `g_pir_pending`); `attachInterrupt(digitalPinToInterrupt(kPirPin), pir_isr, RISING)` wired in `setup()` after `power_manager.begin()` and gated by `kPirWakeEnabled`. The `loop()` consumes the pending flag inside `noInterrupts()`/`interrupts()` brackets so a motion edge since the last loop forces a stay-awake decision.
- **`phase2/camera-node-firmware/include/wildlife/power_policy.h`** — new pure `constexpr should_grant_boot_grace(now_ms, grace_until_ms)` helper using wrap-safe `uint32` subtraction (~24.8-day half-period); zero Arduino dependencies.
- **`phase2/camera-node-firmware/src/power_mgmt.cpp` / `include/.../power_mgmt.h`** — `PowerManager::begin()` records `boot_grace_until_ms_ = millis() + kWakeBootGraceMs`; `maybe_sleep()` short-circuits while `should_grant_boot_grace(now, deadline)` is true so the detection loop captures at least one frame after a PIR wake.
- **`phase2/camera-node-firmware/include/wildlife/net_wifi.h`** — pure `constexpr next_wifi_backoff_ms(attempt, base_ms, max_ms)` capped-exponential WiFi reconnect helper, overflow-safe via 64-bit intermediate, native-testable. Backed by new `WILDLIFE_WIFI_BACKOFF_BASE_MS` / `WILDLIFE_WIFI_BACKOFF_MAX_MS` config tunables (with `static_assert` invariants).
- **`scripts/_pi_creds.py`** — `Credentials` `@dataclass(frozen=True)` with `Credentials.load_from_env()` and `as_legacy_tuple()` shim. New optional `PI_KEY` env var enables public-key SSH auth alongside the legacy password fallback. Host/user resolution is now delegated to `_pi_targets.resolve_target("display")` so the loader holds **no literal LAN IPs**.
- **`scripts/_pi_targets.py`** — pure `resolve_target(name, *, env, file_loader, fallback)` with precedence YAML file (`PI_TARGETS_FILE`, default `~/.wildlife/pi-targets.yaml`) → env vars (`CAMERA_IP`/`CAMERA_USER`, `PI_HOST`/`PI_USER`) → caller-supplied fallback. Replaces hard-coded LAN IPs in verify scripts.
- **`pi-display-node/tests/test_pi_creds.py`** — 9 new cases over `Credentials.load_from_env` / `as_legacy_tuple` / legacy `load()` covering target-resolution failure, key-only, password-only, both-set, neither-set, and `SystemExit(2)` on missing `PI_PASS`.
- **`pi-display-node/tests/test_pi_targets.py`** — 14 cases over in-memory env + injected `file_loader`: yaml-wins, env fallback, default user, explicit fallback, no-source RuntimeError, malformed-entry fall-through, unknown-name RuntimeError, default loader on missing file, real-YAML round-trip, empty YAML returns None, non-mapping top-level raises ValueError, list-form `targets:` falls through, scalar entry falls through, explicit-user honoured.
- **`pi-display-node/tests/test_ssh_client.py`** — 4 new cases for the `connect()` auth matrix: key-only, password-only (legacy), key+password (encrypted-key flow), and missing-both-raises.
- **52 Unity native tests** (up from 39): 4 new `should_grant_boot_grace` cases (within / boundary / after / wrap-safe), 3 per-channel topic-shape cases, 4 `next_wifi_backoff_ms` cases (attempt 0/1/N/saturation), 2 score-edge cases (`class_id_from_target` high-byte ignore, `track_max_score` saturation at uint16 max).

### Changed

- **`scripts/_ssh_client.py` `connect()`** — kwarg-additive: new `key_filename: str | None = None`, `password` becomes optional. Key-present path enables `allow_agent=True` / `look_for_keys=True`; password-only keeps legacy safe defaults. Raises `ValueError` when both are `None`. All existing callers continue to work unchanged via the legacy positional `password` arg.
- **`deploy.py`** — threads `PI_KEY` env through `paramiko.SSHClient.connect()`. Default unset path keeps existing password-only flow byte-for-byte.
- **`scripts/verify_pi_live.py`** — replaces literal `192.168.4.30` with `_pi_targets.resolve_target("camera")`; **no literal fallback**. Camera-target resolution happens lazily inside `main()` (via `_resolve_camera_ip()`), and misconfiguration exits with a friendly `error: cannot resolve camera target …` message + `sys.exit(2)` instead of an import-time stack trace.
- **`pyproject.toml`** — `[tool.coverage.run] source` extended to include `scripts/` (with `omit` for `verify_*.py`, `deploy.py`, `read_xiao_serial.py` which require live hardware). New helpers (`_pi_creds`, `_pi_targets`, `_mqtt_client`, `_ssh_client`) are now under the 85 % gate.
- **`.agents/harness.toml`** — harness `test` task adds `--cov=scripts` so the orchestrator-driven gate matches `pyproject.toml`.
- **`.gitignore`** — adds `pi-targets.yaml` and `.wildlife/` so a project-local copy of the targets file is never committed.

### Fixed

- Removed all remaining hard-coded LAN IPs (`192.168.4.21` × 3 in `_pi_creds.py`, `192.168.4.30` fallback in `verify_pi_live.py`). Targets now flow exclusively through `_pi_targets.resolve_target` with the documented YAML→env→fallback precedence.

---

## [Previous] — Phase 2 PIR Wake-Source Classification & Type Safety

### Added

- **`phase2/camera-node-firmware/include/wildlife/pir_event.h`** — `constexpr should_accept_pir_edge()` debounce helper using `uint32_t` subtraction for wrap-safe `micros()` comparison; zero Arduino dependencies, fully native-testable.
- **`phase2/camera-node-firmware/include/wildlife/power_policy.h`** extended with `WakeSource` enum (`kColdBoot`, `kPirExt0`, `kTimer`, `kUnknown`), `kEspWakeCauseUndefined/Ext0/Timer` constants, and `classify_wake_source()` pure function mapping `esp_sleep_get_wakeup_cause()` numerics to typed enum values.
- **`phase2/camera-node-firmware/src/power_mgmt.cpp`** — `PowerManager::begin()` now classifies the boot wake source; `last_wake_source()` accessor exposed on the class. Native stub returns `kColdBoot` unconditionally.
- **39 Unity native tests** (up from 29): 4 for `classify_wake_source`, 4 for `should_accept_pir_edge` (first edge, within window, exact boundary, uint32 wrap-around), 1 for `last_wake_source()` accessor, 1 for new config constants, plus all pre-existing tests.
- **`config.h` tunables**: `WILDLIFE_PIR_DEBOUNCE_MS` (250 ms, overridable) and `WILDLIFE_WAKE_BOOT_GRACE_MS` (500 ms, overridable) macros promoted to `kPirDebounceMs` / `kWakeBootGraceMs` namespace constants.
- **Expanded mypy typecheck scope** — harness `typecheck` task and `pyproject.toml` now cover `scripts/` and `deploy.py` in addition to kiosk and tests (24 source files total).

### Fixed

- **20 mypy type errors resolved** across 9 files:
  - Removed 9 stale `# type: ignore[import-untyped]` / `# type: ignore` comments — `paramiko ≥ 3.0` now ships a `py.typed` marker (with the `types-paramiko` stub package pinned in dev deps for CI parity), and the workspace-local stubs under `typings/paho/` cover the `paho-mqtt 1.x` line that this repo still pins.
  - `scripts/verify_pi_roundtrip.py` and `scripts/verify_pi_diagnose.py`: `rc` now typed as `int` via `int(stdout.channel.recv_exit_status())` to satisfy `no-any-return`.
  - `scripts/verify_e2e_journey.py`: `chan.send()` argument changed from `str` to `bytes` (`.encode()`), matching `paramiko.Channel.send` signature.
  - `scripts/_mqtt_client.py`: replaced explicit-kwarg + `**extra` pattern with a single merged dict to avoid `"Client gets multiple values for keyword"` error under mypy's duplicate-kwarg check.
  - `pi-display-node/tests/test_ssh_client.py`: added `from typing import cast`; all `build_ssh_client()` return values cast to `_FakeClient`; `connect()` call sites with `_FakeClient` instances annotated with `# type: ignore[arg-type]` at the monkeypatch boundary.

### Changed

- `.gitignore` extended with: `dist/`, `build/`, editor swap files (`.swp`, `.swo`, `*~`, `.DS_Store`, `Thumbs.db`), `.env` / credential files, compiled ML artifacts (`*.onnx`, `*.tflite`, `*.vela.tflite`, `*.h5`), firmware binaries (`firmware.bin`, `firmware.elf`, `bootloader.bin`, `partitions.bin`).

---

## Previous — Phase 2 Power Management Testability & Export Manifest

### Fixed (review-pass 2)

- **Race in `verify_e2e_journey.py`**: step 3/4 now polls the Pi's `observations.db` for up to 12 s instead of a single read, waiting for both the detection row and (when injected) the populated `thumb_jpeg` column. Adds a 250 ms inter-publish gap between detection and retained thumbnail to prefer in-order processing on the kiosk side.
- **MITM exposure in `deploy.py`**: SSH host-key handling now defaults to `paramiko.RejectPolicy()` after loading the user's `known_hosts`. Set `PI_HOST_KEY_POLICY=auto` (logs a warning) to opt back into `AutoAddPolicy`. `PI_KNOWN_HOSTS` overrides the host-key file location.
- **Camera-node embedded broker shutdown race** (`camera-node-firmware/tests/conftest.py`): replaced abrupt `loop.call_soon_threadsafe(loop.stop)` teardown with a cooperative `stop_requested: threading.Event` plus `await broker.shutdown()`, mirroring the pi-display-node fixture. Eliminates `Event loop stopped before Future completed` errors in session teardown.
- **Path resolution in camera conftest**: `include/secrets.h` and the `pio run` working directory are now anchored to `Path(__file__).resolve().parent.parent`, so `pytest camera-node-firmware/tests` works regardless of `cwd`.
- **Unusable placeholder `secrets.h`**: when `FLASH_FIRMWARE=1` and `secrets.h` is missing, the fixture now reads `WIFI_SSID` / `WIFI_PASSWORD` (and optionally `MQTT_BROKER_FIRMWARE`) from the environment and `pytest.fail`s with a clear message if either is missing — no more silently-flashed devices with `YOUR_SSID` / `YOUR_PASSWORD`.
- **HIL thumbnail tests on stock Grove model**: `test_thumbnail_published` and `test_thumbnail_topic_contains_frame_id` are now `@pytest.mark.skipif`-gated on `THUMBNAILS_ENABLED=1`, since the stock Phase 1 firmware skips JPEG publishing when `AI.last_image()` returns nothing (see `docs/07-next-steps.md` §Camera-side Thumbnail Preview).
- **Misleading docstring** in `scripts/verify_pi_roundtrip.py`: clarified that the script is read-only Pi diagnostics, with a pointer to `verify_e2e_journey.py` for actual MQTT round-trips.
- **Late-joiner test compatibility**: `test_hardware_integration.py::test_status_message_is_retained` now uses the shared `_make_client()` helper from `conftest.py`, picking up the paho-mqtt v1/v2 callback-API auto-detection introduced in the previous review pass.

### Added

- Live end-to-end user-journey validator at `scripts/verify_e2e_journey.py`. Four-stage check against the deployed pipeline: (1) confirms the real XIAO camera is publishing `wildlife/status/<node>` heartbeats, (2) injects a synthetic-camera detection plus retained base64 JPEG thumbnail to the production broker, (3) SSHes to the Pi and verifies the row landed in `/var/lib/wildlife/observations.db` with every column matching the injected payload, (4) byte-compares the stored `thumb_jpeg` BLOB against the bytes published. Exit code 0 only when every stage passes.
- Operational Pi-diagnostic script suite under `scripts/`: `verify_pi_live.py` (broker liveness + heartbeat watch), `verify_pi_diagnose.py` (mosquitto + kiosk + DB triage), `verify_pi_deepdive.py` (deeper systemd / log inspection), `verify_pi_roundtrip.py` (synthetic publish + DB read-back), and `read_xiao_serial.py` (timed serial capture from the camera).
- Shared SSH-credential loader `scripts/_pi_creds.py`: every Pi-touching script now reads `PI_HOST` / `PI_USER` / `PI_PASS` from the environment (no secrets in source).
- New integration-test slice and harness tasks (`integration-kiosk-mqtt`, `integration-firmware-format`, `integration-schema-parity`, `integration-manifest-parity`, `integration-all`) that prove the kiosk MQTT lifecycle, firmware thumbnail framing, SQLite schema parity, and class-table/manifest parity end-to-end without Mosquitto.
- Cross-component integration & E2E roadmap at `docs/08-integration-e2e-plan.md`.
- `typings/` directory with PEP 561 stubs for `paho.mqtt.client` and `amqtt.broker` so the kiosk and integration tests typecheck without third-party stub dependencies.
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
- Added `phase2/camera-node-firmware/include/wildlife/pir_event.h` with `should_accept_pir_edge()`, a `constexpr` debounce helper using `uint32_t` subtraction for wrap-safe `micros()` comparison; no Arduino dependency.
- Extended `phase2/camera-node-firmware/include/wildlife/power_policy.h` with `WakeSource` enum, `kEspWakeCauseUndefined/Ext0/Timer` local constants, and `classify_wake_source()` pure function mapping `esp_sleep_get_wakeup_cause()` numerics to enum values — native-testable without `<esp_sleep.h>`.
- Extended `config.h` with `WILDLIFE_PIR_DEBOUNCE_MS` (250 ms, overridable) and `WILDLIFE_WAKE_BOOT_GRACE_MS` (500 ms, overridable) macros lifted to `kPirDebounceMs` / `kWakeBootGraceMs` namespace constants.
- Extended `PowerManager::begin()` to classify boot wake source; `last_wake_source()` accessor exposed on the class. Native stub returns `kColdBoot` unconditionally.
- Extended Unity native test suite from 29 to 39 tests: 4 for `classify_wake_source`, 4 for `should_accept_pir_edge` (first edge, within window, exact boundary, uint32 wrap-around), 1 for `last_wake_source()` in native, 1 for new config constants.
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
- Added auto-generated `phase2/camera-node-firmware/.gitignore` (from `pio project init --ide vscode`) so PlatformIO build output and per-project IDE metadata stay out of the PR surface.

### Fixed

- Removed hard-coded Pi SSH password (`M@ng0M00`) from `deploy.py` and all `verify_pi_*.py` scripts; routed every credential through `scripts/_pi_creds.load()` reading `PI_PASS` (and `BROKER_PASS` for `deploy.py`).
- Documented the SSCMA `last_image()` thumbnail caveat in `camera-node-firmware/src/main.cpp`: `AI.invoke(...,show=true)` regresses detection on the stock Grove Vision AI V2 model, so the firmware keeps `AI.invoke()` defaults and skips thumbnail publishing quietly until a preview-capable model is deployed.
- `pi-display-node/install.sh` now installs apt prerequisites (mosquitto, sqlite3, python3-venv, PyQt5, X server stack), respects `BROKER_USER`/`BROKER_PASS` env vars for unattended runs, and points `sqlite3 < schema/observations.sql` at the correct path next to the script.
- `pi-display-node/mosquitto/wildlife.conf` no longer redeclares `persistence`/`log_dest` from Debian's base `mosquitto.conf`, eliminating duplicate-config warnings on broker start.
- Set the XIAO `upload_speed` back to a stable `460800` after the 921600 setting proved unreliable on the USB-CDC adapter; documented the `esptool ... --before usb_reset` 115k fallback in the firmware bring-up notes.
- Hardened kiosk regressions around MQTT lifecycle, UI edge flows, storage behavior, and thumbnail handling.
- Added editor-compatibility wrappers and stub headers for the original firmware tree and the Phase 2 firmware tree.
- Removed stale Jetson-oriented scope from project documentation and phase planning.
- Repaired the firmware SSCMA thumbnail and class-name integration for the current Seeed library contract in both the shipped and Phase 2 firmware paths.
- Restored PlatformIO native test discovery for the Phase 2 firmware suite and aligned embedded builds on the required C++17 mode.
