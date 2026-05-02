---
name: memory-curate
description: "Curate the agent harness Markdown memory: rotate the MEMORY.md index, inspect episodic logs, and prune stale entries. Use when the runtime control loop has been running for a long horizon and the index has grown beyond the configured rotation threshold."
argument-hint: "Optional reason for the curate pass."
user-invocable: true
---

# Memory Curate

## When To Use
- After a long Ralph or runtime-loop session.
- When `.agents/memory/MEMORY.md` exceeds the `rotate_after_bytes` configured in `.agents/harness.toml` (default 65536).
- Before a release, to compact accumulated decisions into a clean index.

## Procedure
1. Inspect the current index: `python .agents/harness/orchestrator.py memory-index`.
2. List episodic logs: `ls .agents/memory/episodic/`.
3. If the index is large or noisy, rotate: `python .agents/harness/orchestrator.py memory-rotate`. The previous content is archived under `MEMORY.md.<timestamp>.rotated.md` and the live index keeps the last `rotate_keep_tail_bytes`.
4. Read the rotated archive and selectively cherry-pick durable insights back into the live index using the `MemoryStore.insert` or `str_replace` tools (or a plain editor).
5. Delete obsolete episodic logs older than the project's retention horizon: `python -c "from pathlib import Path; [p.unlink() for p in Path('.agents/memory/episodic').glob('*.md') if ...]"`.

## Safety
- Never edit `.agents/memory/episodic/*.md` after the fact; treat them as immutable history.
- `MEMORY.md` is committed to git; rotated archives and episodic logs are gitignored.
