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

- Ruff passes on the full lint target set configured by the harness — `pi-display-node/kiosk`, `pi-display-node/tests`, `scripts`, `deploy.py`, `camera-node-firmware/tests`, and `.agents/harness/orchestrator.py`.
- mypy passes on **24 source files** (kiosk module, tests, `scripts/`, `deploy.py`, and `.agents/harness/orchestrator.py`).
- pytest 92/92 passes.
- Coverage remains at or above 85% (currently **99.01%** across `pi-display-node/kiosk` + the testable `scripts/` helpers `_pi_creds`, `_pi_targets`, `_ssh_client`, `_mqtt_client`).

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
- **52 Unity native tests pass** (class_names; MQTT thumb-budget / topic-format helpers; per-channel topic-shape; runtime config-constant exposure; PowerManager stubs + `last_wake_source()`; pure sleep-decision policy; SSCMA detection-decode helpers; `classify_wake_source()` (all enum variants); `should_accept_pir_edge()` (first-edge / within-window / boundary / uint32 wrap); `should_grant_boot_grace()` (within / boundary / after / wrap-safe); `next_wifi_backoff_ms()` (attempt 0/1/N/saturation/huge-attempt); `class_id_from_target` high-byte ignore; `track_max_score` uint16 saturation; PIR + wake-boot-grace config constants)
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
- Phase 2 native test count (currently **52**)
- mypy scope (currently **24 source files** including `scripts/`, `deploy.py`, and `.agents/harness/orchestrator.py`)
- Coverage gate scope (currently `pi-display-node/kiosk` + `scripts/_pi_creds.py` + `scripts/_pi_targets.py` + `scripts/_ssh_client.py` + `scripts/_mqtt_client.py`; `verify_*.py` / `read_xiao_serial.py` / `deploy.py` are explicitly omitted because they require live hardware)

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

## Test 9: Pi target resolution + SSH key fallback (manual)

Run this when `scripts/_pi_targets.py`, `scripts/_pi_creds.py`, `scripts/_ssh_client.py`, or `deploy.py` change. It does **not** require the camera node — only an SSH-reachable Pi.

### Resolution precedence

```powershell
# 1. YAML beats env. Create a one-off targets file:
$tmp = New-TemporaryFile
@"
targets:
  display:
    host: <pi-ip-from-yaml>
    user: <pi-user>
"@ | Set-Content $tmp
$env:PI_TARGETS_FILE = $tmp.FullName
$env:PI_HOST = '203.0.113.99'   # bogus on purpose; YAML must win
$env:PI_PASS = '<pi-ssh-password>'
.\.venv\Scripts\python.exe -c "from _pi_targets import resolve_target; print(resolve_target('display'))"
Remove-Item env:PI_TARGETS_FILE, env:PI_HOST, env:PI_PASS
Remove-Item $tmp
```

Expected: prints `Target(host='<pi-ip-from-yaml>', user='<pi-user>')`.

```powershell
# 2. Env beats fallback when YAML is absent.
$env:PI_HOST = '<pi-ip>'; $env:PI_USER = '<pi-user>'; $env:PI_PASS = '<pw>'
.\.venv\Scripts\python.exe scripts/verify_pi_live.py   # should ping the env-supplied host
Remove-Item env:PI_HOST, env:PI_USER, env:PI_PASS
```

```powershell
# 3. No source: helper raises RuntimeError, not a silent default.
.\.venv\Scripts\python.exe -c "from _pi_targets import resolve_target; resolve_target('camera')"
```

Expected: `RuntimeError: Cannot resolve Pi target 'camera'…` (no LAN literal in the message).

### SSH key auth fallback

```powershell
# Public-key path: PI_KEY set, PI_PASS unset.
$env:PI_KEY  = "$HOME\.ssh\id_ed25519"
$env:PI_HOST = '<pi-ip>'; $env:PI_USER = '<pi-user>'
.\.venv\Scripts\python.exe scripts/verify_pi_diagnose.py
Remove-Item env:PI_KEY, env:PI_HOST, env:PI_USER
```

Expected: SSH connects via `~/.ssh/id_ed25519` (and ssh-agent / `look_for_keys=True`); `paramiko` does **not** prompt for a password.

```powershell
# Encrypted-key path: PI_KEY + PI_PASS both set; PI_PASS may be the key
# passphrase or the SSH login password (paramiko tries both). PI_PASS is
# also used by deploy.py for the on-Pi `sudo -S` step, so it cannot be
# omitted here.
$env:PI_KEY  = "$HOME\.ssh\id_ed25519_encrypted"
$env:PI_PASS = '<key-passphrase-or-login-password>'
$env:PI_HOST = '<pi-ip>'; $env:PI_USER = '<pi-user>'
$env:BROKER_PASS = '<broker-password>'   # required by deploy.py
.\.venv\Scripts\python.exe deploy.py
Remove-Item env:PI_KEY, env:PI_PASS, env:PI_HOST, env:PI_USER, env:BROKER_PASS
```

Expected: `deploy.py` connects via `_ssh_client.connect(key_filename=…, password=…)` and proceeds with the rsync + installer flow on the Pi. (`deploy.py` does not currently expose a `--dry-run` switch; abort with `Ctrl-C` after the connect line if you only want to verify SSH.)

```powershell
# Neither set: connect() must raise ValueError before any network call.
.\.venv\Scripts\python.exe -c "from _ssh_client import build_ssh_client, connect; connect(build_ssh_client(), 'h', 'u')"
```

Expected: `ValueError: connect() requires either key_filename= or password=`.
