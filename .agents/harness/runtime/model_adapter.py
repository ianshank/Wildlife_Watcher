"""Model-agnostic adapter Protocol with two reference implementations.

The runtime never imports an LLM SDK directly. Instead, anything driving the
control loop must satisfy :class:`ModelAdapter`. The repo ships two reference
adapters:

* :class:`EchoModel` — deterministic stub used by the test suite.
* :class:`LocalCommandModel` — bridges to a configured local CLI through
  :class:`SafeRunner`. Disabled by default; enabled by pointing
  ``[runtime].default_model`` at it.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .logging_ext import get_runtime_logger
from .subprocess_safe import SafeRunner


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelTurn:
    rationale: str
    tool_calls: tuple[ToolCall, ...]
    final: bool


@runtime_checkable
class ModelAdapter(Protocol):
    name: str

    def reason(
        self,
        *,
        system: str,
        history: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> ModelTurn: ...


class EchoModel:
    """Deterministic stub: emits a scripted sequence of :class:`ModelTurn`."""

    def __init__(
        self,
        script: Sequence[ModelTurn],
        *,
        name: str = "echo",
        logger: logging.Logger | None = None,
    ) -> None:
        self.name = name
        self._script: list[ModelTurn] = list(script)
        self._cursor = 0
        self._logger = logger or get_runtime_logger("model.echo")

    def reason(
        self,
        *,
        system: str,
        history: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> ModelTurn:
        if self._cursor >= len(self._script):
            raise IndexError("EchoModel script exhausted")
        turn = self._script[self._cursor]
        self._cursor += 1
        self._logger.debug(
            "echo.turn=%d tool_calls=%d final=%s",
            self._cursor, len(turn.tool_calls), turn.final,
        )
        return turn

    @property
    def remaining(self) -> int:
        return len(self._script) - self._cursor


class LocalCommandModel:
    """Spawn a local CLI and parse stdout JSON into a :class:`ModelTurn`.

    Failures (non-zero exit, malformed JSON, timeout) surface as a turn with
    no tool calls and ``final=False`` so the loop can continue with the
    rationale containing the error.
    """

    def __init__(
        self,
        runner: SafeRunner,
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        name: str = "local-cmd",
        logger: logging.Logger | None = None,
    ) -> None:
        self.name = name
        self._runner = runner
        self._command = tuple(command)
        self._cwd = cwd or Path.cwd()
        self._logger = logger or get_runtime_logger("model.local")

    def reason(
        self,
        *,
        system: str,
        history: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> ModelTurn:
        payload = json.dumps(
            {"system": system, "history": list(history), "tools": list(tools)},
        )
        result = self._runner.run(
            self._command,
            cwd=self._cwd,
            extra_env={"WILDLIFE_HARNESS_MODEL_INPUT": payload},
        )
        if result.returncode != 0 or result.timed_out:
            self._logger.warning(
                "local-cmd failure rc=%s timed_out=%s",
                result.returncode, result.timed_out,
            )
            return ModelTurn(
                rationale=f"local-cmd error rc={result.returncode}",
                tool_calls=(),
                final=False,
            )
        # If the runner spilled the full payload, prefer the file (head+tail
        # may be split across the truncation boundary and produce invalid JSON).
        raw = (
            result.spilled_path.read_text(encoding="utf-8")
            if result.spilled_path is not None
            else (result.stdout_head + result.stdout_tail)
        )
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._logger.warning("local-cmd JSON parse failure: %s", exc)
            return ModelTurn(
                rationale=f"local-cmd JSON decode error: {exc}",
                tool_calls=(),
                final=False,
            )
        return _turn_from_dict(decoded)


def _turn_from_dict(data: Mapping[str, Any]) -> ModelTurn:
    raw_calls = data.get("tool_calls", []) or []
    calls = tuple(
        ToolCall(name=str(item.get("name", "")), arguments=dict(item.get("arguments", {})))
        for item in raw_calls
    )
    return ModelTurn(
        rationale=str(data.get("rationale", "")),
        tool_calls=calls,
        final=bool(data.get("final", False)),
    )
