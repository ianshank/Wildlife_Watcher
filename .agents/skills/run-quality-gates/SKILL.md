---
name: run-quality-gates
description: "Run Wildlife Watcher ruff, mypy, pytest, coverage, and ML pipeline checks through the repo harness. Use for lint, typecheck, regression, quality gate, and pre-merge validation tasks."
argument-hint: "Optional dry-run flag or reason for running the quality gate."
user-invocable: true
---

# Run Quality Gates

## When To Use
- Validate a change before review or merge.
- Reproduce the repo-standard ruff, mypy, pytest, coverage, and ML pipeline flow.
- Confirm that setup and CI use the same commands.

## Procedure
1. Activate the project virtual environment.
2. Run `python .agents/harness/orchestrator.py quality`.
3. When the slice touches `ml-pipeline/`, also run `python .agents/harness/orchestrator.py ml-pipeline-lint`, `ml-pipeline-typecheck`, `ml-pipeline-test`, and `ml-pipeline-smoke`.
4. If the gate fails, rerun the narrow failing command before editing more code.
5. Report the smallest failing slice, not the entire repo history.