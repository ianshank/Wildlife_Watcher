---
name: ralph-loop
description: "Drive the Ralph loop: outer while-loop that runs the inner control loop or topology until acceptance passes, max iterations is hit, or a stuck-state window is detected. Use only after a SPEC shard exists; do NOT use for exploratory work."
argument-hint: "Optional --intent and --max-iterations; otherwise defaults from .agents/harness.toml."
user-invocable: true
---

# Ralph Loop

## When To Use
- Execution phase of a well-specified task. The discovery and specification phases must already be complete (use `spec-shard-init` first).
- When mechanical retries against `lint`/`typecheck`/`test` are the right path to green.

## Do Not Use For
- Exploratory or open-ended problem-solving — Ralph will burn iterations without convergence.
- Tasks lacking a verifiable acceptance signal.

## Procedure
1. Confirm the SPEC slice is in place: `ls .agents/memory/spec/<slice-id>/`.
2. Dry-run first: `python .agents/harness/orchestrator.py ralph-run --intent "<summary>" --max-iterations 2 --dry-run`.
3. For real runs, omit `--dry-run`. Acceptance defaults: `[runtime].acceptance_tasks` (currently `lint`, `typecheck`, `test`).
4. Inspect outcome:
   - `completed=True reason=accepted` — green, move on.
   - `completed=False reason=stuck` — the same set of acceptance tasks failed for `[ralph].stuck_window` consecutive iterations. Stop, read `.agents/memory/episodic/<today>.md`, fix the underlying issue, then re-run.
   - `completed=False reason=max_iterations` — raise `[ralph].max_iterations` only if telemetry shows real progress per iteration; otherwise the task is mis-scoped.

## Safety
- Ralph honors `[ralph].require_acceptance_before_signal=true` — even if the model says `final`, Ralph re-checks acceptance before signaling done.
- Stuck-state action is `[ralph].stuck_action` ∈ `{escalate, abort, sleep}`.
