# Next Steps - Phase 2/3 Development

This document outlines follow-on work after the Phase 2 hardware-wiring & ops-hardening PR is merged.

## Phase 2: PIR Wake & Deep Sleep — remaining hardware wiring

The host-testable policy + ISR + boot-grace are complete. What remains is on-device validation:

- [x] Wire `should_accept_pir_edge()` into `main.cpp` ISR handler (debounce on the interrupt line)
- [x] Wire `kWakeBootGraceMs` into `PowerManager::maybe_sleep()` post-PIR grace period so brief detection bursts don't immediately re-enter deep sleep
- [x] WiFi reconnect backoff helper (`next_wifi_backoff_ms`) with `static_assert`-guarded config tunables
- [ ] Add hardware validation on XIAO ESP32S3 Sense (on-device PIR cycling: trigger PIR, observe deep-sleep entry, confirm wake, check that camera heartbeat resumes on `wildlife/status/<node>`)
- [ ] Document power consumption measurements (active polling vs PIR-gated sleep duty cycle)
- [ ] Hardware-in-the-loop CI runner (deferred — see ADR-tba) once a self-hosted runner with a wired XIAO is available.

## Phase 2: Operational hardening — completed in this slice

- [x] `Credentials` dataclass + optional `PI_KEY` public-key SSH path in `_ssh_client.connect()`, `deploy.py`, and `verify_*.py`.
- [x] `_pi_targets.resolve_target` removes all hard-coded LAN IPs from `scripts/`. YAML→env→fallback precedence with full unit-test coverage.
- [x] Coverage gate extended to `scripts/_pi_creds`, `_pi_targets`, `_ssh_client`, `_mqtt_client` (≥ 85 %; currently 99 %).

## Phase 2: Network Module Testing

- Extend Unity test coverage for `net_mqtt.*` (topic formatting, publish lifecycle)
- Add tests for `net_wifi.*` (connection, reconnection policy)
- Add edge-case tests for `sscma_io.*` (sensor polling, detection shaping)

## Phase 2: Module Integration

- Validate modular firmware composition in hardware environment
- Test power budget with real PIR and sleep cycles

### Backport to Phase 1

- Consider promoting `class_names.h`, `pir_event.h`, and `power_policy.h` patterns to Phase 1 firmware baseline
- Evaluate merging successful Phase 2 modules back into main firmware tree once hardware-validated

## Phase 3: ML Pipeline Integration

### ExportManifest Usage

- Integrate `ExportManifest` into YOLO export workflow
- Use manifest for linking exported ONNX/TFLite models to class labels
- Generate kiosk-compatible metadata from training runs

### Dataset Preparation

- Extend CUB-200-2011 dataset helpers for wildlife-specific use cases
- Add data augmentation pipeline validation
- Create wildlife dataset splits for training/validation/test

### Model Export Pipeline

- Complete YOLO → ONNX → TFLite conversion pipeline
- Add Vela optimization for Ethos-U55 target
- Validate int8 quantization accuracy
- Generate deployment-ready models for Grove Vision AI V2

### Deployment Integration

- Test exported models on Grove Vision AI V2 hardware
- Validate detection accuracy against baseline models
- Document model deployment workflow via SenseCraft

## Testing & Quality

### Coverage Expansion

- Maintain 85%+ branch coverage as new modules are added (currently 98.87%)
- Add hypothesis property tests for critical data transformations
- Extend Unity test suite as firmware modules grow (currently 39 native tests)

### CI/CD Enhancement

- Add hardware-in-the-loop testing if feasible
- Add model export validation to CI pipeline
- Add firmware binary size tracking

### Documentation

- Keep ARCHITECTURE.md synchronized with component evolution
- Update regression checklist as new validation surfaces are added
- Document power consumption profiles for different wake/sleep configurations

## Infrastructure

### Git Worktree Migration

- Evaluate moving Phase 2/3 from in-repo subdirectories to dedicated worktrees
- Maintain compatibility with existing harness command surface
- Update documentation if migration occurs

### Tooling

- Enhance harness orchestrator with parallel task execution if needed
- Add firmware binary size reporting to harness
- Add model performance benchmarking commands


## Timeline Considerations

- Phase 2 PIR/sleep implementation: Next priority after this PR
- Phase 3 model export integration: Can proceed in parallel with Phase 2 hardware work
- Coverage expansion: Ongoing as new code is added
- Documentation: Continuous updates as components evolve

## Success Criteria

- Phase 2: Functioning PIR wake + deep sleep with <10μA sleep current, validated via Unity tests and hardware measurements
- Phase 3: End-to-end pipeline producing Grove Vision AI V2-compatible models with ≥90% detection accuracy on wildlife classes
- Quality: Maintain 85%+ coverage, all harness gates green, comprehensive documentation

## Operational Tooling and Live E2E

The `feature/integration-e2e-validation` work landed a four-stage live end-to-end validator (`scripts/verify_e2e_journey.py`) and a Pi-diagnostic script suite under `scripts/`. Follow-on:

- Wire `verify_e2e_journey.py` into a post-deploy gate (e.g. a `setup_and_test.ps1` opt-in flag or a manual GitHub Actions workflow_dispatch job that runs against a self-hosted runner on the Pi network).
- Add an opt-in CI job that runs `integration-all` on every PR (currently runs locally via the harness).
- Replace SSH password auth with key-based auth in `_pi_creds.py` and `deploy.py`; keep `PI_PASS` only as a fallback for first-run bootstrap.
- Capture run artifacts (`verify_e2e_journey.py` output + DB row dump) into `reports/` on each successful sign-off.

## Camera-side Thumbnail Preview

The Phase 1 firmware currently skips thumbnail publishing because the stock Grove Vision AI V2 model does not emit a preview JPEG, and forcing `AI.invoke(...,show=true)` regresses detection (see the header comment in `camera-node-firmware/src/main.cpp`).

- Export a custom YOLO model with image output enabled through the Phase 3 `ml-pipeline/` export path.
- Once deployed to the Grove board, switch the firmware call to `AI.invoke(1, false, true)` and re-run `verify_e2e_journey.py` with the real camera as the publisher (no synthetic injection) to prove end-to-end thumbnail flow.
- Add a kiosk-side dashboard counter for `thumbs_received` so operators can spot a regression in the preview path immediately.

## Open Questions

- Should class_names.h pattern be backported to Phase 1 immediately or wait for full Phase 2 validation?
- What wildlife classes should be prioritized for custom model training?
- Should we add model performance regression testing to CI?
- Is hardware-in-the-loop testing feasible for PIR/sleep validation?
