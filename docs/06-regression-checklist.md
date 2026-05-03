# 06 — Regression Checklist

Run this checklist before packaging a reviewer-facing change set. It extends the smoke-test flow from `04-bring-up.md` with the repo's automated gates and the phase-isolated validation surfaces.

## Preflight

- Confirm the workspace uses the repo virtual environment under `.venv/`.
- Confirm the broker, kiosk config, and firmware secrets still live in config files or templates rather than source edits.
- If the change touches documentation only, still run the baseline quality gate so the repo stays green as a whole.

## Test 1: Baseline repo quality gate

From `wildlife-watcher-phase1/`:

```powershell
python .agents/harness/orchestrator.py quality
```

Expected result:

- Ruff passes on 24 source files (kiosk + tests + scripts + deploy.py + orchestrator).
- mypy passes on 24 source files (expanded scope now includes `scripts/` and `deploy.py`).
- pytest 64/64 passes.
- Coverage remains at or above 85% (currently 98.87% on the kiosk module).

## Test 2: Kiosk smoke path

If the kiosk code or MQTT contract changed, rerun the install-free smoke checks from the harness and the existing bring-up notes.

```powershell
python .agents/harness/orchestrator.py mock-publish-detection --dry-run
```

Then verify the expectations in `04-bring-up.md` still hold:

- status topics reflect online and offline transitions
- detection JSON remains parseable by the kiosk
- thumbnails still map to the expected `frame_id`

## Test 3: AGENTS coverage

If any `AGENTS.md` file changed, confirm the directory guidance still covers the repo surface.

```powershell
python .agents/harness/orchestrator.py agents-md-coverage
```

Expected result:

- all required directories remain covered
- no new non-trivial subtree is missing local agent guidance

## Test 4: Phase 2 firmware regression slice

If the Phase 2 firmware tree changed and PlatformIO is available locally, run:

```powershell
python .agents/harness/orchestrator.py firmware-build
python .agents/harness/orchestrator.py firmware-test-native
python .agents/harness/orchestrator.py firmware-build-phase2
```

Expected result:

- the shipped Phase 1 firmware baseline still builds against the current SSCMA and MQTT library surface
- **39 Unity native tests pass** (covering class_names, MQTT thumb-budget/topic-format helpers, runtime config-constant exposure, PowerManager stubs + `last_wake_source()` accessor, pure sleep-decision policy, SSCMA detection-decode helpers, `classify_wake_source()` with all enum variants, `should_accept_pir_edge()` with first-edge / within-window / exact-boundary / uint32-wraparound cases, PIR + wake-boot-grace config constants)
- the hardware build still resolves the modular networking and power-management layers (both `seeed_xiao_esp32s3` and `seeed_xiao_esp32s3_pir` envs)

If PlatformIO is not installed, record that gap explicitly in the PR summary instead of silently skipping it.

## Test 5: Phase 3 ML pipeline regression slice

If the ML pipeline changed, run the full typed export path:

```powershell
python .agents/harness/orchestrator.py ml-pipeline-lint
python .agents/harness/orchestrator.py ml-pipeline-typecheck
python .agents/harness/orchestrator.py ml-pipeline-test
python .agents/harness/orchestrator.py ml-pipeline-smoke
```

Expected result:

- Ruff passes on the typed `numpy` export path and tests
- mypy passes on 27 ml-pipeline source files (100% coverage)
- pytest passes on all 57 export and augmentation tests (including hypothesis property tests)
- the CPU-only ONNX smoke check completes without requiring a Jetson runtime

## Test 6: Cross-component parity checks

If the change touches MQTT topic formatting, thumbnail encoding, the SQLite schema, kiosk storage writes, firmware class table, or export manifest labels, run:

```powershell
python .agents/harness/orchestrator.py integration-kiosk-mqtt
python .agents/harness/orchestrator.py integration-firmware-format
python .agents/harness/orchestrator.py integration-schema-parity
python .agents/harness/orchestrator.py integration-manifest-parity
python .agents/harness/orchestrator.py integration-all
```

Expected result:

- the kiosk can subscribe to an embedded broker and persist a full status + detection + thumbnail flow without Mosquitto
- firmware thumbnail topics and base64 payloads still round-trip into the kiosk thumbnail event contract
- the kiosk test suite initializes SQLite from `pi-display-node/schema/observations.sql` rather than an inline duplicate
- `Storage` reads and writes remain compatible with the checked-in schema and index set
- the committed export-manifest fixture stays aligned with the Phase 2 `WILDLIFE_CLASS_NAMES` table

## Test 7: Reviewer handoff docs

Before opening a PR, verify these reviewer entry points are still accurate:

- `README.md`
- `ARCHITECTURE.md`
- `CHANGELOG.md`
- `docs/06-regression-checklist.md`

Each of those files should agree on three facts:

- the Phase 1 baseline remains the stable deployment path
- Phase 2 native test count (currently **39**)
- mypy scope (currently **24 source files** including scripts + deploy.py)


Expected result:

- Ruff passes on the typed `numpy` export path and tests
- mypy passes on the `ml-pipeline` package
- pytest passes on the export and augmentation tests (14 tests including ExportManifest validation and hypothesis property tests)
- the CPU-only ONNX smoke check completes without requiring a Jetson runtime

## Test 6: Cross-component parity checks

If the change touches MQTT topic formatting, thumbnail encoding, the SQLite schema, kiosk storage writes, firmware class table, or export manifest labels, run:

```powershell
python .agents/harness/orchestrator.py integration-kiosk-mqtt
python .agents/harness/orchestrator.py integration-firmware-format
python .agents/harness/orchestrator.py integration-schema-parity
python .agents/harness/orchestrator.py integration-manifest-parity
python .agents/harness/orchestrator.py integration-all
```

Expected result:

- the kiosk can subscribe to an embedded broker and persist a full status + detection + thumbnail flow without Mosquitto
- firmware thumbnail topics and base64 payloads still round-trip into the kiosk thumbnail event contract
- the kiosk test suite initializes SQLite from `pi-display-node/schema/observations.sql` rather than an inline duplicate
- `Storage` reads and writes remain compatible with the checked-in schema and index set
- the committed export-manifest fixture stays aligned with the Phase 2 `WILDLIFE_CLASS_NAMES` table

## Test 7: Reviewer handoff docs

Before opening a PR, verify these reviewer entry points are still accurate:

- `README.md`
- `ARCHITECTURE.md`
- `CHANGELOG.md`
- `docs/06-regression-checklist.md`

Each of those files should agree on three facts:

- the Phase 1 baseline remains the stable deployment path
- Phase 2 is isolated under `phase2/`
- Phase 3 stays off-device for training and targets export back to the Grove Vision AI V2 path

## Validation Gaps

- The repo is Git-backed now, but GitHub repository settings should still be checked so the default branch is `main` rather than stale `civ` metadata.
- PlatformIO-based checks depend on a local toolchain and may need to be called out as not run.
- The broader MQTT broker, thumbnail reassembly, and host-level system-integration slices remain planned in `08-integration-e2e-plan.md` and are not automated yet.

## Test 8: Live end-to-end user-journey validation

Run this against the deployed Pi + camera before sign-off when any of the following changed: firmware MQTT publish path, kiosk subscribe / parse / persist path, SQLite schema, or thumbnail framing. It is the only check in this checklist that touches real hardware.

Prerequisites: the camera is powered, the Pi is reachable on the LAN, and you know the Pi SSH password and broker password.

```powershell
$env:PI_PASS   = '<pi-ssh-password>'
$env:MQTT_PASS = '<broker-password>'
.\.venv\Scripts\python.exe scripts/verify_e2e_journey.py
Remove-Item env:PI_PASS; Remove-Item env:MQTT_PASS
```

Expected result (exit code 0):

- **step1** observes a `wildlife/status/<camera-node-id>` heartbeat from the real XIAO within 10 seconds.
- **step2** publishes a synthetic detection plus a retained base64 thumbnail to the production broker as `e2e-test-cam` and both publishes are acked.
- **step3** finds the unique `frame_id` in `/var/lib/wildlife/observations.db` over SSH and confirms every column (`ts`, `node_id`, `frame_id`, `class_name`, `class_id`, `confidence`, `bbox_*`, `model`) matches the injected payload.
- **step4** byte-compares the stored `thumb_jpeg` BLOB against the JPEG sent in step 2 — proves the base64 → MQTT → `ThumbCache.put` (QImage validation) → `Storage.update_thumb` chain is intact.

If step 1 fails but the rest pass, the kiosk pipeline is healthy and the camera node needs investigation (see `05-troubleshooting.md` and `scripts/verify_pi_diagnose.py`). If step 4 fails after step 3 passes, the JPEG is reaching the kiosk but `ThumbCache.put` is rejecting it as an invalid image — common when a model export changes the JPEG framing.
