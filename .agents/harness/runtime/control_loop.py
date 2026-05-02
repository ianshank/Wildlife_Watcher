"""Deterministic control loop: intent -> context -> reason -> act -> verify -> loop.

The :class:`ControlLoop` decouples reasoning (model) from execution (tools)
exactly as described in the article. The loop terminates when the model emits
``final=True`` *and* the :class:`AcceptanceChecker` reports zero exit codes
across all configured acceptance tasks; otherwise it loops up to
``runtime.max_iterations``.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .config import RuntimeConfig
from .logging_ext import CorrelationFilter, get_runtime_logger
from .memory import MemoryStore
from .model_adapter import ModelAdapter, ModelTurn


@dataclass(frozen=True)
class Intent:
    summary: str
    acceptance_tasks: tuple[str, ...]
    extra_context: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class LoopResult:
    accepted: bool
    iterations: int
    last_acceptance: Mapping[str, int]
    correlation_id: str
    transcript: tuple[str, ...]


class ToolRegistry:
    """Maps tool name -> callable taking a JSON-like dict and returning anything."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable[[Mapping[str, Any]], Any]] = {}

    def register(self, name: str, fn: Callable[[Mapping[str, Any]], Any]) -> None:
        if name in self._tools:
            raise KeyError(f"Tool already registered: {name}")
        self._tools[name] = fn

    def call(self, name: str, args: Mapping[str, Any]) -> Any:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name](args)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))


class AcceptanceChecker:
    def __init__(self, command_runner: Callable[[str], int]) -> None:
        self._runner = command_runner

    def check(self, task_names: Sequence[str]) -> dict[str, int]:
        return {name: self._runner(name) for name in task_names}


class ControlLoop:
    def __init__(
        self,
        cfg: RuntimeConfig,
        *,
        model: ModelAdapter,
        tools: ToolRegistry,
        memory: MemoryStore,
        acceptance: AcceptanceChecker,
        logger: logging.Logger | None = None,
        correlation: CorrelationFilter | None = None,
    ) -> None:
        self._cfg = cfg
        self._model = model
        self._tools = tools
        self._memory = memory
        self._acceptance = acceptance
        self._logger = logger or get_runtime_logger("control_loop")
        self._correlation = correlation

    def _new_correlation_id(self) -> str:
        if self._correlation is not None:
            return self._correlation.new_correlation_id()
        return f"{self._cfg.correlation_prefix}-{uuid.uuid4().hex[:12]}"

    def run(self, intent: Intent) -> LoopResult:
        cid = self._new_correlation_id()
        transcript: list[str] = [f"intent: {intent.summary}"]
        history: list[Mapping[str, Any]] = [
            {"role": "user", "content": intent.summary},
        ]
        last_acceptance: Mapping[str, int] = {}
        accepted = False
        iteration = 0
        max_iters = self._cfg.max_iterations
        for iteration in range(1, max_iters + 1):
            self._logger.info(
                "loop.iter cid=%s iteration=%d/%d", cid, iteration, max_iters,
            )
            turn = self._model.reason(
                system=f"intent: {intent.summary}",
                history=history,
                tools=[{"name": name} for name in self._tools.names()],
            )
            transcript.append(f"turn {iteration}: {turn.rationale}")
            history.append({"role": "assistant", "content": turn.rationale})
            for call in turn.tool_calls:
                try:
                    result = self._tools.call(call.name, call.arguments)
                    transcript.append(f"tool {call.name} -> {result!r}")
                    history.append(
                        {
                            "role": "tool",
                            "name": call.name,
                            "result": result,
                        }
                    )
                except Exception as exc:
                    self._logger.warning(
                        "tool.failure cid=%s tool=%s error=%s", cid, call.name, exc,
                    )
                    transcript.append(f"tool {call.name} ERROR {exc}")
                    history.append(
                        {"role": "tool", "name": call.name, "error": str(exc)}
                    )
            self._memory.gc_heartbeat(iteration)
            if turn.final:
                last_acceptance = self._acceptance.check(intent.acceptance_tasks)
                accepted = all(code == 0 for code in last_acceptance.values())
                self._logger.info(
                    "loop.acceptance cid=%s accepted=%s codes=%s",
                    cid, accepted, dict(last_acceptance),
                )
                if accepted:
                    transcript.append("acceptance: pass")
                    break
                transcript.append(f"acceptance: fail {dict(last_acceptance)}")
        else:
            self._logger.warning(
                "loop.max_iterations cid=%s iterations=%d", cid, iteration,
            )
        self._memory.append_episodic(
            f"[{cid}] iterations={iteration} accepted={accepted} intent={intent.summary}"
        )
        return LoopResult(
            accepted=accepted,
            iterations=iteration,
            last_acceptance=dict(last_acceptance),
            correlation_id=cid,
            transcript=tuple(transcript),
        )


def make_default_turn(
    rationale: str = "",
    *,
    final: bool = True,
) -> ModelTurn:
    """Convenience helper used by callers that need a no-op terminal turn."""

    return ModelTurn(rationale=rationale, tool_calls=(), final=final)
