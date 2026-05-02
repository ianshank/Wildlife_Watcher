---
name: phase-worktree-bootstrap
description: "Bootstrap a dedicated Wildlife Watcher roadmap worktree for Phase 2 PIR/power or Phase 3 ML work. Use for worktree setup, branch isolation, and phase-scoped experimentation."
argument-hint: "Specify phase2 or phase3 and the target worktree path."
user-invocable: true
---

# Phase Worktree Bootstrap

## When To Use
- Start roadmap work that should not land directly on `main`.
- Separate Phase 2 firmware/power work from Phase 3 ML pipeline work.
- Keep experimental dependencies and artifacts out of the stable tree.

## Procedure
1. Choose the phase scope and a clean worktree path such as `../ww-phase2` or `../ww-phase3`.
2. Create the worktree with `git worktree add` and a phase-specific branch.
3. Activate the venv or create a worktree-local one as needed.
4. Run `.agents/harness/orchestrator.py quality --dry-run` before starting edits so the worktree inherits the same repo contract.