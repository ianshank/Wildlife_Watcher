---
name: agents-md-coverage
description: "Verify that every required Wildlife Watcher directory has an AGENTS.md file. Use for agent customization maintenance, repo hygiene, and hierarchy validation."
argument-hint: "Optional dry-run or follow-up action for missing directories."
user-invocable: true
---

# AGENTS Coverage Check

## When To Use
- Confirm the repo hierarchy is fully annotated for agents.
- Catch missing directory-level guidance after moving or adding code.
- Validate the current customization surface before relying on subagents.

## Procedure
1. Run `python .agents/harness/orchestrator.py agents-md-coverage`.
2. If directories are missing `AGENTS.md`, add the smallest directory-local guidance needed.
3. Re-run the coverage check before closing the task.