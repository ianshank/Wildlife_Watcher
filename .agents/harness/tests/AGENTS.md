# Runtime Tests Agent Guide

## Scope
- Unit and integration tests for the `.agents/harness/runtime/` package.
- Coverage floor: 85% (enforced by `runtime-test` harness command).

## Conventions
- Markers: `unit` (default, fast, no real subprocess), `integration` (spawns the orchestrator), `hardware` (none here).
- Fixtures live in `conftest.py`. All are `tmp_path`-rooted; never write to `.agents/memory/` from a test.
- File naming: `test_<module>_<aspect>.py` for narrow tests; `test_<module>.py` for the omnibus.

## Standard Commands
- All runtime tests: `python .agents/harness/orchestrator.py runtime-test`
- Lint runtime + tests: `python .agents/harness/orchestrator.py runtime-lint`
- Mypy runtime + tests: `python .agents/harness/orchestrator.py runtime-typecheck`
- Combined gate: `python .agents/harness/orchestrator.py quality-runtime`
