"""Ralph loop driver: outer while-loop with stuck-state detection.

The driver wraps a :class:`ControlLoop` (or any :class:`Topology`) and keeps
calling it until acceptance passes, max iterations is hit, or a stuck-state
window is detected. Programmatic backpressure means: even if the inner says
``final``, we re-check acceptance before signaling done when
``require_acceptance_before_signal`` is true.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from .config import RalphConfig
from .control_loop import AcceptanceChecker, ControlLoop, Intent, LoopResult
from .logging_ext import get_runtime_logger
from .memory import MemoryStore


@dataclass(frozen=True)
class RalphReport:
    completed: bool
    reason: str
    iterations: int
    last_acceptance: dict[str, int]
    correlation_ids: tuple[str, ...]


class _Innerable(Protocol):
    def run(self, intent: Intent) -> Sequence[LoopResult] | LoopResult: ...


class RalphDriver:
    def __init__(
        self,
        cfg: RalphConfig,
        *,
        inner: _Innerable | ControlLoop,
        acceptance: AcceptanceChecker,
        memory: MemoryStore,
        sleeper: Callable[[float], None] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._cfg = cfg
        self._inner = inner
        self._acceptance = acceptance
        self._memory = memory
        self._sleeper = sleeper or (lambda _s: None)
        self._logger = logger or get_runtime_logger("ralph")

    def is_stuck(self, recent: Sequence[LoopResult]) -> bool:
        if len(recent) < self._cfg.stuck_window:
            return False
        window = list(recent[-self._cfg.stuck_window :])
        baseline = {k for k, v in window[0].last_acceptance.items() if v != 0}
        if not baseline:
            return False
        for item in window[1:]:
            failing = {k for k, v in item.last_acceptance.items() if v != 0}
            if failing != baseline:
                return False
        return True

    def _run_inner(self, intent: Intent) -> list[LoopResult]:
        outcome = self._inner.run(intent)
        if isinstance(outcome, LoopResult):
            return [outcome]
        return list(outcome)

    def drive(self, intent: Intent) -> RalphReport:
        recent: list[LoopResult] = []
        correlation_ids: list[str] = []
        last_codes: dict[str, int] = {}
        max_iters = self._cfg.max_iterations
        iteration = 0
        for iteration in range(1, max_iters + 1):
            self._logger.info("ralph.iter iteration=%d/%d", iteration, max_iters)
            results = self._run_inner(intent)
            recent.extend(results)
            for r in results:
                correlation_ids.append(r.correlation_id)
            inner_accepted = all(r.accepted for r in results)
            if self._cfg.require_acceptance_before_signal:
                last_codes = self._acceptance.check(intent.acceptance_tasks)
                acceptance_pass = all(c == 0 for c in last_codes.values())
            else:
                last_codes = dict(results[-1].last_acceptance)
                acceptance_pass = inner_accepted
            self._memory.append_episodic(
                f"ralph.iter={iteration} inner={inner_accepted} acceptance={acceptance_pass}"
            )
            if inner_accepted and acceptance_pass:
                self._logger.info("ralph.accepted iteration=%d", iteration)
                return RalphReport(
                    completed=True,
                    reason="accepted",
                    iterations=iteration,
                    last_acceptance=last_codes,
                    correlation_ids=tuple(correlation_ids),
                )
            if self.is_stuck(recent):
                action = self._cfg.stuck_action
                self._logger.warning("ralph.stuck action=%s", action)
                if action == "abort":
                    return RalphReport(
                        completed=False,
                        reason="stuck",
                        iterations=iteration,
                        last_acceptance=last_codes,
                        correlation_ids=tuple(correlation_ids),
                    )
                if action == "sleep":
                    self._sleeper(self._cfg.sleep_seconds_on_stuck)
                    recent.clear()
                    continue
                if action == "escalate":
                    return RalphReport(
                        completed=False,
                        reason="stuck",
                        iterations=iteration,
                        last_acceptance=last_codes,
                        correlation_ids=tuple(correlation_ids),
                    )
        self._logger.warning("ralph.max_iterations iterations=%d", iteration)
        return RalphReport(
            completed=False,
            reason="max_iterations",
            iterations=iteration,
            last_acceptance=last_codes,
            correlation_ids=tuple(correlation_ids),
        )
