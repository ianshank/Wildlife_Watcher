"""Hardened subprocess wrapper used by the runtime.

Adds: timeout enforcement, env scrubbing (allowlist + denylist substrings),
head/tail truncation of large output (full payload spilled to disk), and
correlation-id propagation. Existing ``orchestrator.run_command`` is left
untouched for back-compat.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .config import SubprocessConfig
from .logging_ext import get_runtime_logger


@dataclass(frozen=True)
class SafeRunResult:
    returncode: int
    stdout_head: str
    stdout_tail: str
    stderr_head: str
    stderr_tail: str
    spilled_path: Path | None
    timed_out: bool
    duration_s: float
    correlation_id: str


class _PopenLike(Protocol):
    def communicate(
        self, input: bytes | None = ..., timeout: float | None = ...
    ) -> tuple[bytes, bytes]: ...

    def kill(self) -> None: ...

    @property
    def returncode(self) -> int | None: ...


PopenFactory = Callable[..., _PopenLike]


class SafeRunner:
    """Run a command with timeout, env scrubbing, and output truncation.

    All collaborators are injected so tests substitute fakes without touching
    the real subprocess machinery.
    """

    def __init__(
        self,
        cfg: SubprocessConfig,
        *,
        spill_root: Path,
        clock: Callable[[], float] = time.monotonic,
        popen: PopenFactory | None = None,
        env_provider: Callable[[], Mapping[str, str]] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._cfg = cfg
        self._spill_root = spill_root
        self._clock = clock
        self._popen: PopenFactory = popen or subprocess.Popen
        self._env_provider = env_provider or (lambda: os.environ.copy())
        self._logger = logger or get_runtime_logger("subprocess")

    def scrub_env(self, env: Mapping[str, str]) -> dict[str, str]:
        allow = set(self._cfg.env_allowlist)
        deny = tuple(self._cfg.env_denylist_substrings)
        scrubbed: dict[str, str] = {}
        for key, value in env.items():
            if key not in allow:
                continue
            upper = key.upper()
            if any(token in upper for token in deny):
                continue
            scrubbed[key] = value
        return scrubbed

    def truncate(self, payload: bytes) -> tuple[str, str, Path | None]:
        head_n = self._cfg.truncate_head_bytes
        tail_n = self._cfg.truncate_tail_bytes
        if len(payload) <= head_n + tail_n:
            decoded = payload.decode("utf-8", errors="replace")
            return decoded, "", None
        head = payload[:head_n].decode("utf-8", errors="replace")
        tail = payload[-tail_n:].decode("utf-8", errors="replace")
        spilled: Path | None = None
        if len(payload) >= self._cfg.spill_threshold_bytes:
            self._spill_root.mkdir(parents=True, exist_ok=True)
            spilled = self._spill_root / f"safe-run-{uuid.uuid4().hex}.log"
            spilled.write_bytes(payload)
            self._logger.warning(
                "Spilled %d bytes of output to %s", len(payload), spilled,
            )
        return head, tail, spilled

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        extra_env: Mapping[str, str] | None = None,
        timeout_s: float | None = None,
        correlation_id: str | None = None,
    ) -> SafeRunResult:
        cid = correlation_id or f"sr-{uuid.uuid4().hex[:8]}"
        deadline = timeout_s if timeout_s is not None else self._cfg.default_timeout_s
        env = self.scrub_env(self._env_provider())
        if extra_env:
            for key, value in extra_env.items():
                env[key] = value
        self._logger.info(
            "safe-run start cid=%s cmd=%s timeout=%s", cid, list(command), deadline,
        )
        started = self._clock()
        proc = self._popen(
            list(command),
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        timed_out = False
        try:
            stdout_b, stderr_b = proc.communicate(timeout=deadline if deadline > 0 else None)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            stdout_b, stderr_b = proc.communicate()
            self._logger.error("safe-run timeout cid=%s after=%ss", cid, deadline)
        duration = self._clock() - started
        out_head, out_tail, spilled_out = self.truncate(stdout_b or b"")
        err_head, err_tail, spilled_err = self.truncate(stderr_b or b"")
        spilled = spilled_out or spilled_err
        rc = proc.returncode if proc.returncode is not None else -1
        self._logger.info(
            "safe-run done cid=%s rc=%s duration=%.3f spilled=%s timed_out=%s",
            cid, rc, duration, spilled, timed_out,
        )
        return SafeRunResult(
            returncode=rc,
            stdout_head=out_head,
            stdout_tail=out_tail,
            stderr_head=err_head,
            stderr_tail=err_tail,
            spilled_path=spilled,
            timed_out=timed_out,
            duration_s=duration,
            correlation_id=cid,
        )


def _ensure_any() -> Any:  # pragma: no cover - kept for type-checker imports
    return None
