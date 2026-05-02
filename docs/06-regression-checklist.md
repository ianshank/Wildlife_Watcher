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

- Ruff passes.
- mypy passes.
- pytest passes.
- coverage remains at or above 85%.

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
python .agents/harness/orchestrator.py firmware-test-native
python .agents/harness/orchestrator.py firmware-build-phase2
```

Expected result:

- native tests pass for reusable helpers and publish-shaping logic
- the hardware build still resolves the modular networking and power-management layers

If PlatformIO is not installed, record that gap explicitly in the PR summary instead of silently skipping it.

## Test 5: Phase 3 ML pipeline regression slice

If the ML pipeline changed, run the full typed export path:

```powershell
python .agents/harness/orchestrator.py ml-pipeline-typecheck
python .agents/harness/orchestrator.py ml-pipeline-test
python .agents/harness/orchestrator.py ml-pipeline-smoke
```

Expected result:

- mypy passes on the `ml-pipeline` package
- pytest passes on the export and augmentation tests
- the CPU-only ONNX smoke check completes without requiring a Jetson runtime

## Test 6: Reviewer handoff docs

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

- This workspace currently has no `.git` metadata, so actual branch, push, and PR creation cannot be validated here.
- PlatformIO-based checks depend on a local toolchain and may need to be called out as not run.
