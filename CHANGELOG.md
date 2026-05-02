# Changelog

All notable changes to this workspace-ready repo slice are documented in this file.

## Unreleased

### Added

- Repo-local agent harness tasks for linting, type checking, testing, AGENTS coverage, firmware validation, and ML pipeline validation.
- Localized `AGENTS.md` guidance across the repo plus reusable agent-facing skills under `.agents/skills/`.
- Phase 2 firmware scaffold under `phase2/camera-node-firmware/` with reusable networking, power, and SSCMA module boundaries.
- Phase 3 `ml-pipeline/` scaffold for typed dataset preparation, export helpers, Vela parsing, and CPU-only smoke validation.
- Reviewer handoff docs: `ARCHITECTURE.md`, `docs/06-regression-checklist.md`, and this changelog.
- Root `.gitignore` for Python caches, PlatformIO output, secrets, SQLite runtime files, and generated ML assets.

### Changed

- Raised the Python quality floor to an enforced 85% coverage threshold via the repo harness.
- Updated `README.md` to surface the harness command set, reviewer navigation, and non-Jetson next steps.
- Standardized workspace-level validation through `setup_and_test.ps1` delegating to `.agents/harness/orchestrator.py quality`.

### Fixed

- Hardened kiosk regressions around MQTT lifecycle, UI edge flows, storage behavior, and thumbnail handling.
- Added editor-compatibility wrappers and stub headers for the original firmware tree and the Phase 2 firmware tree.
- Removed stale Jetson-oriented scope from project documentation and phase planning.
