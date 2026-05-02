from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_runtime_dirs_have_agents_md() -> None:
    expected = [
        REPO_ROOT / ".agents" / "harness" / "runtime",
        REPO_ROOT / ".agents" / "harness" / "tests",
        REPO_ROOT / ".agents" / "memory",
    ]
    for path in expected:
        assert (path / "AGENTS.md").is_file(), f"AGENTS.md missing at {path}"
