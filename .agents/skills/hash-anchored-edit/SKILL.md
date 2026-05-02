---
name: hash-anchored-edit
description: "Apply file edits using the harness HashAnchoredEditor: every line carries a content hash; mismatched hashes abort the write before corruption. Use when programmatically modifying source files where another agent or human may have raced you."
argument-hint: "Optional path or rationale for the edit."
user-invocable: false
---

# Hash-Anchored Edit

## When To Use
- Any time the runtime control loop must mutate a source file under contention.
- Whenever an automated edit pipeline (Ralph loop, topology worker) writes to disk without a human in the diff loop.

## Contract
- Each line is annotated with a `sha256` prefix of length `[edits].hash_prefix_length` (default 12).
- `apply_edit` re-reads the file, re-anchors, and compares against the `expected` digests.
- Behavior on mismatch: governed by `[edits].mismatch_behavior`.
  - `abort` (default) — raise `HashMismatchError`; no bytes written.
  - `warn` — log and proceed (only enable for one-shot scripts).

## Procedure
1. Annotate the live file: `editor.annotate(path.read_text())`.
2. Build the `expected` and `replacement` `AnchoredLine` sequences.
3. Call `editor.apply_edit(path, expected=..., replacement=...)`.
4. On `HashMismatchError`: re-read the file, re-anchor, re-plan the edit. Do not retry blindly — the file changed for a reason.

## Notes
- Hashes are computed over `\n`-normalized line content; CRLF/LF differences do not trigger spurious mismatches.
- The editor never appends a trailing newline to empty replacements.
