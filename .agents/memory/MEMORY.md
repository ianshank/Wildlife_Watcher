# MEMORY index

This is the long-term, human-curated semantic memory for the Wildlife Watcher
agent harness runtime. It is intentionally tiny: a compressed directory of
durable decisions and pointers to deeper context.

## Conventions

- One short bullet per durable decision. No prose paragraphs.
- Add a date prefix in `YYYY-MM-DD` form when relevant.
- Episodic detail belongs in `.agents/memory/episodic/<date>.md` (gitignored).
- Spec shards live under `.agents/memory/spec/<slice-id>/` (committed).

## Durable Decisions

- 2026-05-02 Initial harness runtime added: `.agents/harness/runtime/` provides ControlLoop, MemoryStore, HashAnchoredEditor, RalphDriver, and six topology patterns; defaults are config-driven from `.agents/harness.toml`.
