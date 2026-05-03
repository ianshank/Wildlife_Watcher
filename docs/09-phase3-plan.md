# Phase 3 Plan — ML Export Pipeline & HIL Validation

> **Branch**: `feat/phase3-ml-export-and-hil-validation`
> **Predecessor**: PR #8 (`feat/phase2-hardware-wiring-and-ops-hardening`) merged into `main` as `dc6de53`.
> **Baseline (main, post-merge)**: 97 pytest @ 99.02 % branch coverage, 52 native Unity tests, 6 CI checks green.

This document is the working plan for the next development slice. It is intentionally backwards-compatible (no
existing command, env-var, topic, or config-key changes), reuses existing harness/orchestrator surfaces, and drives
all tunables through `config.h` macros / `config.yaml` / env vars (no hard-coded values).

---

## 1. Guiding Principles (carried forward)

| Principle | How it is enforced |
| --- | --- |
| **No hard-coded values** | New tunables land as `WILDLIFE_*` macros in `config.h` (firmware) or `config.yaml` keys + env-var overrides (Python). Reviewed against `grep -nE "192\\.168\\.|broker\\.local"` before push. |
| **Backwards compatible** | New code paths are kwarg-additive (`def f(x, *, new=None)`); legacy positional/3-tuple shims kept. New harness tasks are additive; existing names stay. |
| **Reusable components** | Pure helpers go into `phase2/.../include/wildlife/*.h` (constexpr, native-testable) or `scripts/_*.py` private modules; both have ≥ 85 % coverage gate. |
| **Strict testing** | Every new firmware constexpr ⇒ Unity case. Every new Python function ⇒ pytest case (mock at I/O boundary, never patch internals). Coverage gate stays ≥ 85 % branch (currently 99.02 %). |
| **Logging + debugging** | New scripts use `logging.getLogger(__name__)` with per-module verbosity, `LOG_LEVEL` env override, structured `extra={}` payloads. New firmware code uses the existing `Serial.printf` debug surface gated by `WILDLIFE_DEBUG_LOG`. |
| **Lint clean** | ruff (E501, I001, F821 + repo defaults), mypy strict (`disallow_untyped_defs`), no `# type: ignore` without comment. |

---

## 2. Outstanding Tech Debt to Sweep Early

These are tracked findings from the previous review rounds. Address in the **first two commits** of this branch
before feature work, so feature CI is uncluttered.

1. **Audit `# type: ignore` comments** — `pi-display-node/tests/test_ssh_client.py` still has
   `# type: ignore[arg-type]` at the monkeypatch boundary. Re-evaluate now that `_FakeClient` is fully typed; if the
   ignores are still required, leave a `# REASON: …` comment per line.
2. **Audit `Any` returns** — search `scripts/` and `pi-display-node/kiosk/` for `-> Any` and tighten where the
   callee return type is known. Flag false positives back to the linter config (`mypy.no_any_return`).
3. **NumPy 2.x readiness in `ml-pipeline/`** — current pin is `numpy>=1.26,<3.0`; scan `wildlife_ml/` for
   `np.float_`, `np.int_`, deprecated `np.product`, `np.in1d` (removed in 2.0). Replace with `np.float64`,
   `np.int64`, `np.prod`, `np.isin`. Pin upper bound only if a specific blocker is found; otherwise allow 2.x.
4. **Ruff rule expansion** — enable `RUF`, `B`, `SIM`, `PTH`, `UP` rule families staged behind `select = [...]`
   updates in `pyproject.toml`, fix the resulting findings, then bump the harness `quality` task to fail on the
   new rules. Land each rule family in its own commit so git-bisect is easy.
5. **Coverage of `verify_*.py`** — currently in the `omit` list because they need live SSH. Carve out the
   pure-CPU portions (arg parsing, message formatting) into private `_verify_*.py` modules with their own tests so
   the coverage list shrinks.
6. **`scripts/deploy.py` dry-run** — the regression checklist documents Ctrl-C as the bail-out today. Add a real
   `--dry-run` flag (no SSH connect, just prints the command plan) so the checklist instruction becomes
   `deploy.py --dry-run` again. Includes new pytest cases.

---

## 3. Workstreams

Each workstream below maps to a sequential set of commits with an opt-in worktree path so two engineers (or two
agent sessions) can work in parallel on different streams without merge collisions.

### W1 — ML Export Pipeline End-to-End  *(skill: aitk, ml-training-orchestrator, neural-network-architect)*

**Goal**: Take a YOLOv8n-tier checkpoint from `ml-pipeline/datasets/` to a Vela-optimised `.tflite` deployable to the
Grove Vision AI V2.

| Step | Deliverable | Test Surface |
| --- | --- | --- |
| W1.1 | `wildlife_ml.train.cli` — typed entry-point that reads `train_config.yaml` (no positional defaults). | Pytest: argparse unit tests, config-validation tests, dry-run mode that doesn't import torch. |
| W1.2 | `wildlife_ml.export.onnx.export_yolo()` — wraps existing `torch.onnx.export` with deterministic opset + dynamic-axes config from YAML. | Pytest: shape/dtype invariants via hypothesis; mock torch at boundary. |
| W1.3 | `wildlife_ml.export.tflite.convert()` — reads ONNX graph, writes int8 TFLite using a representative-dataset callable that the user injects (no hard-coded path). | Pytest: round-trip a 1×3×H×W tensor through a stub graph; assert manifest links the generated artifact. |
| W1.4 | `wildlife_ml.export.vela.optimize()` — calls `vela` CLI via `subprocess.run(...)`, captures `vela_summary.csv`, parses into `VelaReport` dataclass. | Pytest: golden-file parser test (already exists for parser); add `optimize()` test with mock subprocess. |
| W1.5 | `wildlife_ml.export.manifest.ExportManifest` extended with `tflite_path`, `vela_report`, `quantization` fields (all `Optional`, additive). | Pytest: round-trip serialization, blank-field tolerance, kiosk-side `from_dict` accepts both old (Phase 1) and new schemas. |
| W1.6 | New harness task `ml-pipeline-export-smoke` running W1.1 → W1.4 against a tiny stub model committed under `ml-pipeline/tests/fixtures/`. | Adds a CI job (extends `.github/workflows/ci.yml` matrix). |

**Backwards-compat**: existing `ExportManifest.from_config()` callers don't break (new fields default to `None`).
**Reusability**: `_subprocess_runner.py` helper added; reused by Vela invocation and any future external CLI step.

### W2 — Hardware-in-the-Loop (HIL) Validation  *(skill: airunway-aks-setup, azure-diagnostics)*

**Goal**: A self-hosted GitHub runner on the Pi network (or a developer workstation with a tethered XIAO) that runs
the live PIR + sleep + thumbnail-publish loop on every push to `main`.

| Step | Deliverable | Test Surface |
| --- | --- | --- |
| W2.1 | `scripts/hil/runner_setup.sh` (POSIX) + `runner_setup.ps1` (Windows) — installs the GitHub Actions runner, registers it under `runs-on: [self-hosted, wildlife-hil]`. No hard-coded tokens; reads from `.env`. | Bash/Pester syntax check via shellcheck/PSScriptAnalyzer. |
| W2.2 | New harness task `hil-pir-loop` — wraps `verify_e2e_journey.py` + `read_xiao_serial.py` and asserts wake-source classification matches expected via Unity-style assertions in Python. | Pytest with `paramiko` mocked + a recorded fixture trace; live mode opt-in via `WILDLIFE_HIL=1`. |
| W2.3 | New `.github/workflows/hil.yml` — `workflow_dispatch` + `schedule` (nightly). Uses `runs-on: [self-hosted, wildlife-hil]`. | Lint via `actionlint` in pre-commit. |
| W2.4 | Power-budget capture — `scripts/hil/measure_power.py` reads INA219 over I²C (lib-pinned), writes CSV to `reports/power-YYYYMMDD.csv`. | Pytest with mocked `smbus2`; coverage gate. |
| W2.5 | `docs/10-hil-runbook.md` — bring-up + recovery instructions. | Linked from `docs/06-regression-checklist.md`. |

**Backwards-compat**: HIL is opt-in; default workflow stays cloud-runner only. Existing `verify_e2e_journey.py`
contract unchanged.

### W3 — Kiosk Telemetry & Thumbnail Counters  *(skill: appinsights-instrumentation, azure-diagnostics)*

**Goal**: Operators can spot a regression in the preview path immediately (per `docs/07-next-steps.md` §
Camera-side Thumbnail Preview).

| Step | Deliverable | Test Surface |
| --- | --- | --- |
| W3.1 | `MqttBridge` exposes `metrics` namedtuple (`detections_received`, `thumbs_received`, `thumbs_decoded`, `last_status_age_s`). Reset path on disconnect. | Pytest with the existing in-process broker fixture. |
| W3.2 | `WildlifeKiosk` adds a status-bar widget bound to `metrics`. Updates ≤ 1 Hz to avoid Qt event-loop pressure. | Pytest with the existing offscreen Qt fixture. |
| W3.3 | Optional Application Insights export gated on `KIOSK_APPINSIGHTS_CONNECTION_STRING` env var (no value ⇒ disabled, no behaviour change). | Pytest with mock telemetry client. |
| W3.4 | `config.yaml` schema bumped (additive only) with `telemetry:` section; `load_config` sets defaults. | Schema parity test extended. |

**Backwards-compat**: telemetry block defaults to `enabled: false`; existing kiosks keep working without config edits.

### W4 — Phase 2 → Phase 1 Backport (gated on HIL)  *(skill: azure-prepare for documentation)*

**Goal**: Once W2 is green, promote PIR-wake + boot-grace + WiFi-backoff helpers from `phase2/` into the production
firmware tree at `camera-node-firmware/`.

| Step | Deliverable | Test Surface |
| --- | --- | --- |
| W4.1 | Vendor `pir_event.h`, `power_policy.h`, `class_names.h`, `net_wifi.h::next_wifi_backoff_ms` into `camera-node-firmware/include/wildlife/`. | New Phase 1 native-test environment in `platformio.ini` (additive `[env:native]`). |
| W4.2 | Re-point Phase 1 `main.cpp` ISR + sleep policy to the vendored helpers. | Bring the Phase 2 native suite (52 tests) into Phase 1 native env. |
| W4.3 | Update `docs/03-xiao-firmware.md` and `04-bring-up.md` with the new wake/sleep budget. | Doc-link checker (`markdown-link-check`). |

**Backwards-compat**: existing Phase 1 binaries continue to flash; the new code paths are off until
`WILDLIFE_PIR_WAKE_ENABLED=1` is defined (matches Phase 2 gate).

### W5 — Operational Robustness  *(skill: azure-diagnostics, azure-rbac)*

| Step | Deliverable | Test Surface |
| --- | --- | --- |
| W5.1 | `_pi_creds.py` — add `PI_KEY_PASSPHRASE` env var support; thread through `_ssh_client.connect(passphrase=…)`. | New pytest cases for the four passphrase × key-only/key+pwd combinations. |
| W5.2 | `deploy.py --dry-run` (item 6 from §2) lands here. | Pytest. |
| W5.3 | `_pi_targets.resolve_target` — accept multi-host display targets (Phase 4 multi-camera prep) via `targets.<name>: [list]`. Backwards-compat: scalar form keeps working. | Pytest. |

---

## 4. Cross-cutting CI Hygiene

- **GitHub Actions caching** — add `actions/cache` for `~/.platformio` (PIO toolchain) and `pip` wheel cache to cut
  CI from ~6 min to ~3 min.
- **Coverage reporter** — upload `coverage.xml` to Codecov (read-only PR comment); no badge change required.
- **Native-test parallelism** — split firmware-test-native and ml-pipeline-test into matrix jobs so failures
  surface independently.
- **Docs check** — pre-commit hook running `markdownlint` on all `docs/*.md`.

---

## 5. Sequencing & Worktrees

```
main
  └─ feat/phase3-ml-export-and-hil-validation   ← this plan + tech-debt sweep (§2)
        ├─ feat/phase3/w1-ml-export             (worktree: ../wildlife-w1)
        ├─ feat/phase3/w2-hil                   (worktree: ../wildlife-w2)
        ├─ feat/phase3/w3-kiosk-telemetry       (worktree: ../wildlife-w3)
        ├─ feat/phase3/w4-phase2-backport       (gated on w2 merge)
        └─ feat/phase3/w5-ops-robustness        (worktree: ../wildlife-w5)
```

**Worktree commands** (Windows-friendly):

```powershell
git worktree add ..\wildlife-w1 -b feat/phase3/w1-ml-export
git worktree add ..\wildlife-w2 -b feat/phase3/w2-hil
# ... merge each via PR back into feat/phase3-ml-export-and-hil-validation
```

W1, W2, W3, W5 are independent and can land in any order. W4 is gated on W2 (HIL must prove the helpers in
hardware before backport). All five reach `main` via a final integration PR off this branch.

---

## 6. Definition of Done (per workstream)

A workstream merges only when **all** the following are true:

1. `python .agents/harness/orchestrator.py quality` exits 0 (ruff + mypy + pytest + ≥ 85 % branch coverage).
2. `python .agents/harness/orchestrator.py firmware-test-native` exits 0 (52 + new cases).
3. `python .agents/harness/orchestrator.py ml-pipeline-test` exits 0.
4. New public symbols documented in `ARCHITECTURE.md` + `CHANGELOG.md` (Unreleased).
5. No new `# type: ignore` without `# REASON: …` comment.
6. `grep -nE "192\\.168\\.|broker\\.local|raspberrypi"` returns zero hits in new code.
7. Reviewer confirms one round of Copilot AI review with zero unresolved comments.

---

## 7. Roadmap Beyond This Branch

| Phase | Focus | Dependency |
| --- | --- | --- |
| Phase 4 | Multi-camera fan-in (≥ 3 nodes), kiosk-side dedup, calendar view. | W3 + W5.3 |
| Phase 5 | Cloud sync (Azure Blob + Event Hub), private LLM-summarised daily digests. | Phase 4 |
| Phase 6 | On-device class retraining via federated-style updates. | Phase 5 + W1 |

---

## 8. Risk Register

| Risk | Mitigation |
| --- | --- |
| Self-hosted runner offline ⇒ HIL CI red on `main`. | `hil.yml` is `workflow_dispatch` + nightly `schedule` only; never blocks PR merges. |
| NumPy 2.x silently changes float32 cast semantics. | §2 item 3 sweep + property tests via hypothesis. |
| Vela CLI version drift breaks parser. | Pin `vela` version in `ml-pipeline/pyproject.toml`; parser tests use golden CSV from pinned version. |
| Phase 2 backport reintroduces a regression in production firmware. | Gate behind `WILDLIFE_PIR_WAKE_ENABLED=1`; keep Phase 1 cold path bit-exact for one release. |
| Encrypted-key passphrase leaks to logs. | `_pi_creds` redacts via existing logger filter; new test asserts `passphrase` is never in `repr()`. |
