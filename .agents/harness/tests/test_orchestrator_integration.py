"""Integration tests for the orchestrator's runtime task surface.

These spawn the orchestrator as a subprocess to validate CLI shape, exit
codes, and back-compat with the existing 13 task names.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.integration


def _orchestrate(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, ".agents/harness/orchestrator.py", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


EXISTING_TASKS = {
    "lint", "typecheck", "test", "quality",
    "firmware-build", "firmware-build-phase2", "firmware-test-native",
    "ml-pipeline-typecheck", "ml-pipeline-lint", "ml-pipeline-test", "ml-pipeline-smoke",
    "agents-md-coverage", "mock-publish-detection",
}

NEW_TASKS = {
    "runtime-lint", "runtime-typecheck", "runtime-test", "quality-runtime",
    "runtime-loop", "ralph-run",
    "memory-rotate", "memory-index", "spec-shard",
    "topology-pipeline", "topology-fanout",
    "topology-producer-reviewer", "topology-expert-pool",
}


def test_help_lists_all_existing_tasks() -> None:
    proc = _orchestrate("--help")
    assert proc.returncode == 0
    for task in EXISTING_TASKS:
        assert task in proc.stdout, f"missing existing task in --help: {task}"


def test_help_lists_all_new_tasks() -> None:
    proc = _orchestrate("--help")
    assert proc.returncode == 0
    for task in NEW_TASKS:
        assert task in proc.stdout, f"missing new task in --help: {task}"


def test_runtime_loop_dry_run_succeeds() -> None:
    proc = _orchestrate("runtime-loop", "--intent", "noop", "--dry-run")
    assert proc.returncode == 0


def test_ralph_run_dry_run_succeeds() -> None:
    proc = _orchestrate(
        "ralph-run", "--intent", "noop", "--max-iterations", "1", "--dry-run",
    )
    assert proc.returncode == 0


def test_spec_shard_requires_id() -> None:
    proc = _orchestrate("spec-shard")
    assert proc.returncode == 2


def test_unknown_task_rejected() -> None:
    proc = _orchestrate("does-not-exist")
    assert proc.returncode != 0
    assert "invalid choice" in proc.stderr


def test_topology_pipeline_dry_run() -> None:
    proc = _orchestrate("topology-pipeline", "--intent", "noop", "--dry-run")
    assert proc.returncode == 0


def test_quality_task_signature_unchanged() -> None:
    """task_quality must short-circuit on first non-zero. Smoke check via --help."""

    proc = _orchestrate("--help")
    assert "quality" in proc.stdout
    assert "quality-runtime" in proc.stdout
