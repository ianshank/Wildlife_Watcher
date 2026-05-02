---
name: spec-shard-init
description: "Scaffold a SPEC.md / task.md / learnings.md vertical slice under `.agents/memory/spec/<id>/`. Use when decomposing a large body of work into isolated execution contracts the runtime can consume sequentially."
argument-hint: "Required slice id, e.g. 2026-05-02-camera-ingest."
user-invocable: true
---

# SPEC Shard Init

## When To Use
- Before driving a long-horizon refactor through Ralph or a multi-agent topology.
- When the existing `MEMORY.md` "spine" needs a new slice for a discrete subproblem.
- To translate a narrative PRD into an immutable execution contract for the runtime.

## Procedure
1. Choose a slice id. Convention: `YYYY-MM-DD-<short-slug>` (no slashes, no spaces).
2. Run `python .agents/harness/orchestrator.py spec-shard --shard-id <slice-id>`.
3. The harness writes three files under `.agents/memory/spec/<slice-id>/`:
   - `SPEC.md` — goals, acceptance criteria, constraints.
   - `task.md` — atomic checkbox list.
   - `learnings.md` — running localized memory register.
4. Optionally pre-populate any of the three with `--shard-spec`, `--shard-task`, `--shard-learnings`.
5. Hand the shard id to the worker layer; they read only that slice's files.

## Output Contract
- Files are written atomically (`.tmp` then `os.replace`).
- Re-running with the same `--shard-id` overwrites the three files. Use a new id for new slices.
