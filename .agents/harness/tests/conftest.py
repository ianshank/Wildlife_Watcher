"""Shared fixtures for the agent harness runtime test suite.

All fixtures are ``tmp_path``-rooted; tests must never write to the real
``.agents/memory/`` directory. Collaborators are constructed via factories so
each test owns the lifetime of the objects it touches.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import textwrap
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

# Make the runtime package importable as the top-level name "runtime".
# `.agents` cannot be a Python package (leading dot), so we add its parent
# `.agents/harness` to sys.path; the `runtime` package then imports cleanly.
_HARNESS_DIR = Path(__file__).resolve().parents[1]
if str(_HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(_HARNESS_DIR))

import runtime  # noqa: E402 — sys.path mutation above is intentional

_HARNESS_TEMPLATE = textwrap.dedent(
    """
    [project]
    name = "test-fixture"
    wildlife_config = "pi-display-node/kiosk/test_config.yaml"
    pythonpath = []

    [commands]
    lint = ["echo", "lint"]
    typecheck = ["echo", "typecheck"]
    test = ["echo", "test"]

    [agent_docs]
    required_paths = []
    ignore_names = []

    [runtime]
    default_model = "echo"
    acceptance_tasks = ["lint", "typecheck", "test"]
    max_iterations = {max_iters}
    iteration_timeout_s = 30
    correlation_prefix = "test"

    [memory]
    root = ".memory"
    index_file = "MEMORY.md"
    episodic_dir = "episodic"
    spec_dir = "spec"
    rotate_after_bytes = {rotate_bytes}
    rotate_keep_tail_bytes = {rotate_keep}
    gc_heartbeat_iterations = {gc_iters}
    atomic_write_suffix = ".tmp"

    [topology]
    pipeline_default_stages = ["a", "b", "c"]
    fanout_default_workers = 3
    expert_pool_min_quorum = 2
    producer_reviewer_max_rounds = 3
    supervisor_escalation_threshold = 2

    [ralph]
    max_iterations = {ralph_max}
    stuck_window = {stuck_window}
    stuck_action = "{stuck_action}"
    sleep_seconds_on_stuck = 0
    require_acceptance_before_signal = {require_accept}
    progress_marker_file = ".ralph_progress"

    [subprocess]
    default_timeout_s = 5
    truncate_head_bytes = {head_bytes}
    truncate_tail_bytes = {tail_bytes}
    spill_dir = "spill"
    spill_threshold_bytes = {spill_thresh}
    env_allowlist = ["PATH", "HOME", "PYTHONPATH"]
    env_denylist_substrings = ["TOKEN", "SECRET"]

    [logging]
    json_fields = ["ts", "level", "logger", "msg", "correlation_id", "task", "iteration"]

    [edits]
    hash_algo = "sha256"
    hash_prefix_length = 8
    mismatch_behavior = "abort"
    """
).strip()


def _bool_str(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


@pytest.fixture
def harness_toml_factory(tmp_path: Path) -> Callable[..., Path]:
    def make(**overrides: Any) -> Path:
        defaults: dict[str, Any] = {
            "max_iters": 5,
            "rotate_bytes": 256,
            "rotate_keep": 64,
            "gc_iters": 2,
            "ralph_max": 5,
            "stuck_window": 2,
            "stuck_action": "abort",
            "require_accept": True,
            "head_bytes": 16,
            "tail_bytes": 16,
            "spill_thresh": 64,
        }
        defaults.update(overrides)
        rendered = _HARNESS_TEMPLATE.format(
            **{k: _bool_str(v) for k, v in defaults.items()}
        )
        path = tmp_path / "harness.toml"
        path.write_text(rendered, encoding="utf-8")
        return path

    return make


@pytest.fixture
def harness_toml(harness_toml_factory: Callable[..., Path]) -> Path:
    return harness_toml_factory()


@pytest.fixture
def runtime_cfg(harness_toml: Path) -> runtime.FullRuntimeConfig:
    return runtime.runtime_config_from_harness(harness_toml)


@pytest.fixture
def memory_root(tmp_path: Path) -> Path:
    root = tmp_path / "memory"
    root.mkdir()
    return root


class FakeClock:
    """Monotonic clock with deterministic step. Each call advances by ``step``."""

    def __init__(self, start: float = 1_000_000.0, step: float = 1.0) -> None:
        self._t = start
        self._step = step

    def __call__(self) -> float:
        value = self._t
        self._t += self._step
        return value


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def frozen_utc() -> Callable[[], datetime]:
    return lambda: datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc)


class FakePopen:
    def __init__(
        self,
        argv: Sequence[str],
        *,
        cwd: str = "",
        env: Mapping[str, str] | None = None,
        outputs: tuple[bytes, bytes] = (b"", b""),
        returncode: int = 0,
        raise_timeout: bool = False,
    ) -> None:
        self.argv = list(argv)
        self.cwd = cwd
        self.env = dict(env or {})
        self._outputs = outputs
        self._returncode = returncode
        self._raise_timeout = raise_timeout
        self.killed = False

    @property
    def returncode(self) -> int | None:
        return self._returncode

    def communicate(
        self, input: bytes | None = None, timeout: float | None = None
    ) -> tuple[bytes, bytes]:
        if self._raise_timeout and not self.killed:
            raise subprocess.TimeoutExpired(self.argv, timeout or 0)
        return self._outputs

    def kill(self) -> None:
        self.killed = True


@pytest.fixture
def fake_popen_factory() -> Callable[..., Callable[..., FakePopen]]:
    def make(
        outputs: tuple[bytes, bytes] = (b"", b""),
        returncode: int = 0,
        raise_timeout: bool = False,
    ) -> Callable[..., FakePopen]:
        def factory(*args: Any, **kwargs: Any) -> FakePopen:
            argv = list(args[0]) if args else list(kwargs.get("args", []))
            return FakePopen(
                argv,
                cwd=kwargs.get("cwd", ""),
                env=kwargs.get("env"),
                outputs=outputs,
                returncode=returncode,
                raise_timeout=raise_timeout,
            )

        return factory

    return make


@pytest.fixture
def safe_runner_factory(
    runtime_cfg: runtime.FullRuntimeConfig,
    tmp_path: Path,
    fake_clock: FakeClock,
    fake_popen_factory: Callable[..., Callable[..., FakePopen]],
) -> Callable[..., runtime.SafeRunner]:
    def make(
        outputs: tuple[bytes, bytes] = (b"ok", b""),
        returncode: int = 0,
        raise_timeout: bool = False,
        env: Mapping[str, str] | None = None,
    ) -> runtime.SafeRunner:
        spill = tmp_path / "spill"
        return runtime.SafeRunner(
            runtime_cfg.subprocess,
            spill_root=spill,
            clock=fake_clock,
            popen=fake_popen_factory(
                outputs=outputs, returncode=returncode, raise_timeout=raise_timeout
            ),
            env_provider=(lambda: dict(env or {"PATH": "/usr/bin"})),
        )

    return make


@pytest.fixture
def memory_store(
    runtime_cfg: runtime.FullRuntimeConfig,
    memory_root: Path,
    frozen_utc: Callable[[], datetime],
) -> runtime.MemoryStore:
    return runtime.MemoryStore(
        runtime_cfg.memory,
        root=memory_root,
        clock=frozen_utc,
    )


@pytest.fixture
def echo_model_factory() -> Callable[..., runtime.EchoModel]:
    def make(turns: Sequence[runtime.ModelTurn]) -> runtime.EchoModel:
        return runtime.EchoModel(script=list(turns))

    return make


@pytest.fixture
def acceptance_factory() -> Callable[..., runtime.AcceptanceChecker]:
    def make(codes: Mapping[str, int]) -> runtime.AcceptanceChecker:
        return runtime.AcceptanceChecker(
            command_runner=lambda name: codes.get(name, 0),
        )

    return make


@pytest.fixture
def correlation_filter(
    runtime_cfg: runtime.FullRuntimeConfig,
) -> runtime.CorrelationFilter:
    counter = {"n": 0}

    def clock() -> float:
        counter["n"] += 1
        return 1234.5 + counter["n"]

    return runtime.CorrelationFilter(
        runtime_cfg.runtime.correlation_prefix,
        clock=clock,
    )


@pytest.fixture(autouse=True)
def _isolated_runtime_logger() -> Any:
    """Reset the wildlife_harness logger between tests so install/teardown is clean."""

    logger = logging.getLogger("wildlife_harness")
    saved_handlers = list(logger.handlers)
    saved_filters = list(logger.filters)
    saved_propagate = logger.propagate
    saved_install_flag = getattr(logger, "_wildlife_runtime_logging_installed", None)
    yield
    logger.handlers[:] = saved_handlers
    logger.filters[:] = saved_filters
    logger.propagate = saved_propagate
    if saved_install_flag is not None:
        logger._wildlife_runtime_logging_installed = saved_install_flag  # type: ignore[attr-defined]
    elif hasattr(logger, "_wildlife_runtime_logging_installed"):
        delattr(logger, "_wildlife_runtime_logging_installed")
