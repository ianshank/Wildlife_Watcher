# Runtime Package Agent Guide

## Scope
- Deterministic control loop + multi-agent topology composition layered on top of the existing task-runner harness in `.agents/harness/orchestrator.py`.
- Persistent Markdown memory (`MemoryStore`), hash-anchored edits (`HashAnchoredEditor`), hardened subprocess wrapper (`SafeRunner`), Ralph driver.

## Module Map
- `config.py`: frozen dataclasses parsed from `.agents/harness.toml`. Defaults live in TOML; do not introduce Python literals here.
- `logging_ext.py`: opt-in JSON formatter and correlation IDs (`WILDLIFE_HARNESS_LOG_FORMAT=json`).
- `subprocess_safe.py`: timeout, env scrub, head/tail truncation, large-output spillage.
- `memory.py`: surgical `view`/`create`/`insert`/`str_replace`/`delete` plus episodic logs, index rotation, SPEC shards.
- `edits.py`: hash-anchored line edits with `HashMismatchError` abort.
- `model_adapter.py`: `ModelAdapter` `Protocol` + `EchoModel` (deterministic) + `LocalCommandModel` (CLI bridge).
- `control_loop.py`: `Intent`, `LoopResult`, `ControlLoop`, `ToolRegistry`, `AcceptanceChecker`.
- `topology.py`: 6 patterns (Pipeline / Fan-out / Expert-pool / Producer-reviewer / Supervisor / Hierarchical).
- `ralph.py`: outer driver with `is_stuck` window and `stuck_action ∈ {escalate, abort, sleep}`.

## Rules
- Every collaborator is constructor-injected. No module-level state besides logger handles.
- All thresholds, timeouts, byte limits, iteration caps live in `.agents/harness.toml` — never hard-code them here.
- Logging: use `get_runtime_logger("<sub>")`. INFO at boundaries, DEBUG inside loops, WARNING on truncation/stuck, ERROR on timeout/mismatch.
- Adding a real LLM means writing a new adapter satisfying `ModelAdapter` (~30 lines). Do NOT modify `ControlLoop` for that.

## Standard Commands
- `python .agents/harness/orchestrator.py runtime-test` — runs this package's pytest suite with `--cov-fail-under=85`.
- `python .agents/harness/orchestrator.py runtime-lint` — ruff over runtime + tests.
- `python .agents/harness/orchestrator.py runtime-typecheck` — mypy over runtime + tests.
- `python .agents/harness/orchestrator.py quality-runtime` — chains the three above.
