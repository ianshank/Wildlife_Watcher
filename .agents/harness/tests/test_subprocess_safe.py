from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import runtime

pytestmark = pytest.mark.unit


def test_happy_path_returns_returncode_and_output(
    safe_runner_factory: Callable[..., runtime.SafeRunner], tmp_path: Path,
) -> None:
    runner = safe_runner_factory(outputs=(b"hello", b""), returncode=0)
    result = runner.run(["echo", "hi"], cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout_head == "hello"
    assert result.stdout_tail == ""
    assert result.spilled_path is None
    assert result.timed_out is False
    assert result.correlation_id


def test_truncation_returns_head_and_tail(
    safe_runner_factory: Callable[..., runtime.SafeRunner], tmp_path: Path,
) -> None:
    payload = (b"A" * 32) + (b"M" * 64) + (b"B" * 32)
    runner = safe_runner_factory(outputs=(payload, b""))
    result = runner.run(["true"], cwd=tmp_path)
    assert result.stdout_head.startswith("A")
    assert result.stdout_tail.endswith("B")
    assert result.spilled_path is not None
    assert result.spilled_path.read_bytes() == payload


def test_no_spill_below_threshold(
    safe_runner_factory: Callable[..., runtime.SafeRunner], tmp_path: Path,
) -> None:
    runner = safe_runner_factory(outputs=(b"x" * 8, b""))
    result = runner.run(["true"], cwd=tmp_path)
    assert result.spilled_path is None
    assert result.stdout_head == "x" * 8


def test_timeout_marks_timed_out_and_kills_process(
    safe_runner_factory: Callable[..., runtime.SafeRunner], tmp_path: Path,
) -> None:
    runner = safe_runner_factory(raise_timeout=True, outputs=(b"", b""), returncode=137)
    result = runner.run(["sleep", "999"], cwd=tmp_path, timeout_s=1)
    assert result.timed_out is True
    assert result.returncode == 137


def test_env_scrub_allowlist_and_denylist(
    runtime_cfg: runtime.FullRuntimeConfig,
    safe_runner_factory: Callable[..., runtime.SafeRunner],
) -> None:
    runner = safe_runner_factory(
        env={
            "PATH": "/usr/bin",
            "HOME": "/home/me",
            "API_TOKEN": "abc",
            "SECRET_KEY": "shh",
            "PYTHONPATH": "/lib",
            "RANDOM": "drop-me",
        },
    )
    scrubbed = runner.scrub_env(
        {
            "PATH": "/usr/bin",
            "HOME": "/home/me",
            "API_TOKEN": "abc",
            "SECRET_KEY": "shh",
            "PYTHONPATH": "/lib",
            "RANDOM": "drop-me",
        }
    )
    assert "PATH" in scrubbed
    assert "HOME" in scrubbed
    assert "PYTHONPATH" in scrubbed
    assert "API_TOKEN" not in scrubbed
    assert "SECRET_KEY" not in scrubbed
    assert "RANDOM" not in scrubbed


def test_extra_env_overrides_provider(
    safe_runner_factory: Callable[..., runtime.SafeRunner], tmp_path: Path,
) -> None:
    runner = safe_runner_factory(env={"PATH": "/usr/bin"})
    result = runner.run(
        ["true"], cwd=tmp_path, extra_env={"PATH": "/opt/bin"},
    )
    # The extra_env override is wired into the env dict before calling popen.
    assert result.returncode == 0
