# Next Steps - Phase 2/3 Development

This document outlines follow-on work after the Phase 2 Power Management Testability & Export Manifest PR is merged.

## Phase 2: Power Management Implementation

### PIR Wake & Deep Sleep
- Implement PIR sensor integration using the PowerManager boundary established in this PR
- Add deep-sleep transitions and wake logic
- Extend Unity test coverage for PIR wake scenarios
- Add hardware validation on XIAO ESP32S3 Sense

### Network Module Testing
- Extend Unity test coverage for `net_mqtt.*` (topic formatting, publish lifecycle)
- Add tests for `net_wifi.*` (connection, reconnection policy)
- Add edge-case tests for `sscma_io.*` (sensor polling, detection shaping)

### Module Integration
- Validate modular firmware composition in hardware environment
- Test power budget with real PIR and sleep cycles
- Document power consumption measurements

### Backport to Phase 1
- Consider promoting `class_names.h` pattern to Phase 1 firmware baseline
- Evaluate merging successful Phase 2 modules back into main firmware tree

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
- Maintain 85%+ branch coverage as new modules are added
- Add hypothesis property tests for critical data transformations
- Extend Unity test suite as firmware modules grow

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

## Open Questions

- Should class_names.h pattern be backported to Phase 1 immediately or wait for full Phase 2 validation?
- What wildlife classes should be prioritized for custom model training?
- Should we add model performance regression testing to CI?
- Is hardware-in-the-loop testing feasible for PIR/sleep validation?
