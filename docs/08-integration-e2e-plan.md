# 08 — Integration and End-to-End Validation Plan

This plan extends the unit-level gates in [06-regression-checklist.md](06-regression-checklist.md) with cross-component integration tiers and a full hardware end-to-end (E2E) walkthrough. It is scoped to the three runtime surfaces in this repo:

- Camera node firmware (Phase 1 baseline + Phase 2 modular slice)
- Display node (Mosquitto broker + PyQt kiosk + SQLite store)
- ML pipeline (offline export path feeding the Grove Vision AI V2 / Ethos-U55 deployment)

It defines what to validate, where the seam lives, the tooling needed, the expected pass criteria, and the sign-off artifact for each tier. All commands assume the repo `.venv` and the `wildlife-watcher-phase1/` working directory unless stated otherwise.

## 1. Goals and Non-Goals

Goals:

- Catch contract drift between firmware publishers and the kiosk subscriber before hardware bring-up.
- Exercise the MQTT topic schema, retained status semantics, thumbnail framing, and SQLite persistence as a single pipeline.
- Validate that ML-pipeline export artifacts (ONNX + manifest + Vela report) match the class table the firmware ships and the labels the kiosk renders.
- Provide a repeatable hardware E2E script for pre-release sign-off.

Non-goals:

- No new Jetson runtime tier; Phase 3 remains offline export only.
- No network-level fuzzing or chaos testing in this plan (tracked separately if needed).
- No replacement of existing unit suites — this plan layers on top of them.

## 2. Test Pyramid for This Repo

| Tier | Scope | Where it runs | Existing or new |
| --- | --- | --- | --- |
| L0 — Static | Ruff + mypy across kiosk, harness, ml-pipeline | `orchestrator.py quality`, `ml-pipeline-lint`, `ml-pipeline-typecheck` | Existing |
| L1 — Unit | Kiosk pytest (≥85% cov), Unity native firmware tests, ml-pipeline pytest | `orchestrator.py test`, `firmware-test-native`, `ml-pipeline-test` | Existing |
| L2 — Component integration | In-process kiosk against an embedded broker; firmware publish helpers against a recorded MQTT consumer; manifest ↔ class-name table parity | New harness tasks below | New |
| L3 — System integration (host) | Firmware native build + simulated detections → real Mosquitto → kiosk → SQLite, all on the dev workstation | New compose-style script | New |
| L4 — Hardware E2E | Grove Vision AI V2 + XIAO ESP32S3 + Pi Zero 2 W + kiosk display, scripted scenario walk-through | Manual, gated by checklist | New (formalized) |

L0 and L1 are already enforced by the harness. The remainder of this plan defines L2–L4.

## 3. Contracts Under Test

These are the seams that must remain stable across phases. Any change to them is a signal to rerun L2+.

- MQTT topic patterns and retained-status semantics defined in `pi-display-node/kiosk/config.yaml` and `pi-display-node/mosquitto/wildlife.conf`.
- Detection JSON shape published by `camera-node-firmware/src/main.cpp` (and mirrored by `phase2/.../net_mqtt.*`) and consumed by `MqttBridge` in `pi-display-node/kiosk/wildlife_kiosk.py`.
- Thumbnail framing helpers in `phase2/camera-node-firmware/include/wildlife/net_mqtt_format.h` (chunk budget, frame-topic format).
- Class-name table in `phase2/camera-node-firmware/include/wildlife/class_names.h` versus `ExportManifest` labels emitted by `ml-pipeline/src/wildlife_ml/export/manifest.py`.
- SQLite schema in `pi-display-node/schema/observations.sql` versus the writes performed by `Storage`.

Each L2/L3 test below names which contract it pins.

## 4. L2 — Component Integration

Goal: lock down each cross-component contract without requiring hardware or a deployed broker.

### 4.1 Kiosk ↔ embedded broker (pins: MQTT topics, retained status, JSON shape)

- Add a pytest module `pi-display-node/tests/test_integration_mqtt.py` that:
  - Spins up an in-process broker (preferred: `amqtt` — already typed via `typings/amqtt/broker.pyi`; fallback: a Mosquitto instance launched via `pytest` fixture using the existing `pi-display-node/mosquitto/wildlife.conf`).
  - Instantiates the kiosk `MqttBridge` and `Storage` against the test broker and a temp SQLite path.
  - Drives traffic via `paho.mqtt.publish.single` (already used by the harness `mock-publish-detection` task).
  - Asserts: status-online retained on connect, status-offline retained on LWT, detection rows persisted with the correct `frame_id`, thumbnails reassembled into `ThumbCache` from chunked frames.
- Wire as a new harness task: `integration-kiosk-mqtt`.
- Pass criteria: deterministic across 50 sequential invocations on Windows + Linux; runtime under 30 s; no flake on retained-message ordering.

### 4.2 Firmware publish helpers ↔ recorded consumer (pins: thumb chunking, topic format)

- Extend `phase2/camera-node-firmware/test/test_native/` with a new Unity case that:
  - Calls `format_frame_topic(...)` and `chunk_thumb_payload(...)` for boundary inputs (zero budget, single byte over budget, exact multiple, max-bounds).
  - Feeds outputs into a host-side Python "recorder" via stdout, captured by a pytest harness in `pi-display-node/tests/test_integration_firmware_format.py`, that re-parses chunks into the same byte stream the kiosk would assemble.
- Wire the Python side into harness task `integration-firmware-format`.
- Pass criteria: byte-for-byte round-trip equality across the recorded fixture set; failure messages cite the offending chunk index.

### 4.3 ML manifest ↔ firmware class table (pins: label parity)

- Add `ml-pipeline/tests/test_manifest_firmware_parity.py` that:
  - Reads `phase2/camera-node-firmware/include/wildlife/class_names.h` via a small text parser (no compilation needed).
  - Loads the latest `ExportManifest` from `ml-pipeline/reports/` (or a fixture for CI).
  - Asserts label count and ordering match, and that `kClassNameCount` equals `len(manifest.labels)`.
- Wire as harness task `integration-manifest-parity`.
- Pass criteria: zero label drift; on mismatch the test prints the diff and the path to whichever side needs updating.

### 4.4 Storage schema ↔ kiosk writes (pins: SQLite schema)

- Add `pi-display-node/tests/test_schema_parity.py` that:
  - Creates a fresh SQLite DB by applying `pi-display-node/schema/observations.sql`.
  - Runs a representative sequence of `Storage` writes.
  - Re-introspects `PRAGMA table_info` and asserts column names, types, and NOT NULL constraints match the schema file.
- Pass criteria: schema file is the single source of truth; any divergence fails the suite.

### 4.5 New harness tasks

Add to `.agents/harness.toml`:

```toml
integration-kiosk-mqtt    = ["{python}", "-m", "pytest", "pi-display-node/tests/test_integration_mqtt.py"]
integration-firmware-format = ["{python}", "-m", "pytest", "pi-display-node/tests/test_integration_firmware_format.py"]
integration-manifest-parity = ["{python}", "-m", "pytest", "{repo_root}/ml-pipeline/tests/test_manifest_firmware_parity.py"]
integration-schema-parity   = ["{python}", "-m", "pytest", "pi-display-node/tests/test_schema_parity.py"]
integration-all             = aggregate of the four above (implemented in orchestrator.py)
```

## 5. L3 — System Integration on the Workstation

Goal: exercise the full message flow on a single machine without hardware, using the real Mosquitto broker config and the kiosk in headless mode.

### 5.1 Topology

- Real Mosquitto launched from `pi-display-node/mosquitto/wildlife.conf` on `localhost:1883`.
- Kiosk launched against `pi-display-node/kiosk/test_config.yaml` with `QT_QPA_PLATFORM=offscreen`.
- Firmware-equivalent traffic generated by:
  1. `orchestrator.py mock-publish-detection` for detection JSON, and
  2. A new `mock-publish-thumbnail` task that uses the Phase 2 chunker logic compiled in the `native` env to emit a byte-accurate thumbnail stream, replayed via `paho`.
- SQLite path is a tmp file; assertions read it after the run completes.

### 5.2 Scenarios

| ID | Scenario | Pass criteria |
| --- | --- | --- |
| S1 | Cold start, single detection | One observation row, one cached thumbnail, status retained as online |
| S2 | Burst (10 detections in 5 s) | 10 rows in correct order, no dropped frames, kiosk feed length stable |
| S3 | Broker disconnect mid-burst | Kiosk transitions to offline, recovers on reconnect, retained status reflects reality |
| S4 | LWT path | Killing the publisher leaves status-offline retained on the topic |
| S5 | Malformed detection JSON | Kiosk logs a parse error, does not crash, does not write a row |
| S6 | Thumbnail with chunk loss | Reassembly fails gracefully; placeholder thumbnail is rendered |

### 5.3 Driver

Add `pi-display-node/tests/system/run_system_integration.py` that orchestrates broker + kiosk + publisher subprocesses with timeouts and structured assertions, plus a `system-integration` harness task. Output is a JSON report under `pi-display-node/tests/system/reports/<timestamp>.json` for archival.

### 5.4 Pass gate

- All six scenarios green.
- Total wall-clock under 3 minutes on the dev workstation.
- Report archived in PR description for any change that touches L2 contracts.

## 6. L4 — Hardware End-to-End

Goal: confirm the deployed stack still satisfies the Phase 1 acceptance criteria from `04-bring-up.md` and the regression rows in `06-regression-checklist.md`.

### 6.1 Required hardware

- Grove Vision AI V2 (Thunderbolt/USB-C to workstation for flashing per `02-grove-flashing.md`).
- XIAO ESP32S3 Sense flashed from `camera-node-firmware/` (Phase 1 baseline) using credentials from `include/secrets.h`.
- Raspberry Pi Zero 2 W running Mosquitto + kiosk service (`pi-display-node/install.sh`, `systemd/wildlife-kiosk.service`).
- Local 2.4 GHz network reachable by all three devices.

### 6.2 Pre-flight

- Repo at the commit under test; `git status` clean.
- L2 + L3 green within the last 24 h on the same commit.
- Grove Vision AI V2 model + class table match the latest `ExportManifest` (verified by L2.3).

### 6.3 Scripted walk-through

1. Power Pi → confirm `mosquitto` and `wildlife-kiosk` services active (`systemctl status`).
2. Power camera node → observe status topic transition to online within 10 s.
3. Trigger a known detection (printed reference image at fixed distance).
4. Confirm: kiosk feed shows the event within 2 s, thumbnail renders, SQLite row written with correct class label and `frame_id`.
5. Repeat for three classes from the class table to cover label-table coverage.
6. Power-cycle the camera → confirm LWT-driven offline status appears on the kiosk.
7. Power camera back on → confirm online status and resumed detections without kiosk restart.
8. Leave the system running for 30 minutes → confirm no memory growth in the kiosk process and no MQTT reconnect storms in `journalctl -u wildlife-kiosk`.

### 6.4 Sign-off artifact

A short Markdown report committed under `docs/handoff/e2e-<date>.md` (gitignored if sensitive) capturing:

- Commit SHA and tag.
- Hardware revisions and firmware build IDs.
- Pass/fail for each step above.
- Photographs or screen captures of the kiosk for at least one detection per class.
- Any deviations from the scripted scenario.

## 7. CI Strategy

- L0 and L1 already run on every push via `.github/workflows/ci.yml`.
- Add an `integration` job that runs L2 tasks on Linux runners. L2.1 and L2.2 require Mosquitto or `amqtt`; install in the workflow.
- L3 runs nightly (cron) on a self-hosted Linux runner where Mosquitto can bind a port. Failures open an issue with the archived JSON report attached.
- L4 stays manual but its sign-off doc is a release-blocking artifact for tagged releases.

## 8. Tooling Additions Summary

- New harness tasks: `integration-kiosk-mqtt`, `integration-firmware-format`, `integration-manifest-parity`, `integration-schema-parity`, `integration-all`, `system-integration`, `mock-publish-thumbnail`.
- New tests: see L2 and L3 sections.
- New CI job: `integration` (per-PR) and `system-integration-nightly` (cron).
- New docs: this file plus a `docs/handoff/` template for L4 sign-off.

## 9. Rollout Sequence

1. Land L2.4 (schema parity) and L2.3 (manifest parity) — lowest cost, highest contract value.
2. Land L2.1 (kiosk ↔ broker) using `amqtt` to keep CI dependency-light.
3. Land L2.2 (firmware format round-trip) once the Phase 2 helpers settle.
4. Land L3 driver and wire the nightly job.
5. Formalize L4 against the next hardware bring-up and store the first sign-off doc as the template.

## 10. Open Questions

- Should L2.1 prefer `amqtt` (Python-only, easier on Windows CI) or a real Mosquitto fixture (closer to production)? Recommendation: `amqtt` for CI, real Mosquitto for L3 only.
- Where does the canonical `ExportManifest` fixture live for L2.3 — committed under `ml-pipeline/tests/fixtures/` or pulled from `ml-pipeline/reports/` at test time? Recommendation: committed fixture, regenerated by an explicit harness task.
- Does L4 need an automated photo-capture rig, or is manual screen capture acceptable for the foreseeable releases? Recommendation: manual until release cadence demands otherwise.
