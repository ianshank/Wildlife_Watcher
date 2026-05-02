---
name: run-quality-gates
description: "Run Wildlife Watcher ruff, mypy, pytest, and coverage checks through the repo harness. Use for lint, typecheck, regression, quality gate, and pre-merge validation tasks."
argument-hint: "Optional dry-run flag or reason for running the quality gate."
user-invocable: true
---

# Run Quality Gates

## When To Use
- Validate a change before review or merge.
- Reproduce the repo-standard ruff, mypy, and pytest flow.
- Confirm that setup and CI use the same commands.

## Procedure
1. Activate the project virtual environment.
2. Run `python .agents/harness/orchestrator.py quality`.
3. If the gate fails, rerun the narrow failing command before editing more code.
4. Report the smallest failing slice, not the entire repo history.