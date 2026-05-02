# Memory Agent Guide

## Scope
- Persistent Markdown memory for the agent harness runtime.
- Two tiers: `MEMORY.md` (committed, human-curated index) and `episodic/YYYY-MM-DD.md` (gitignored daily journals).
- SPEC shards live under `spec/<slice-id>/` and are committed.

## Layout
- `MEMORY.md` — long-term semantic index. Tiny, durable, human-edited.
- `episodic/` — daily logs written by the runtime. Gitignored.
- `spec/<slice-id>/` — `SPEC.md`, `task.md`, `learnings.md` for one vertical slice.
- `*.rotated.md` — index rotation archives. Gitignored.
- `.ralph_progress` — Ralph driver progress marker. Gitignored.

## Rules
- Never edit `episodic/*.md` after the fact. Treat as immutable history.
- `MEMORY.md` is the only file in this tree humans edit by hand.
- Use the `memory-curate` skill for rotation and pruning, not ad-hoc shell commands.
- Tests must root the `MemoryStore` at a `tmp_path`; never write into this real directory from a test.

## Standard Commands
- View index: `python .agents/harness/orchestrator.py memory-index`
- Rotate index: `python .agents/harness/orchestrator.py memory-rotate`
- Create slice: `python .agents/harness/orchestrator.py spec-shard --shard-id <id>`
