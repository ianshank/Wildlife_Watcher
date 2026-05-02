from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
import runtime

pytestmark = pytest.mark.unit


def test_loads_all_sections(harness_toml: Path) -> None:
    cfg = runtime.runtime_config_from_harness(harness_toml)
    assert cfg.runtime.default_model == "echo"
    assert cfg.runtime.acceptance_tasks == ("lint", "typecheck", "test")
    assert cfg.memory.index_file == "MEMORY.md"
    assert cfg.topology.fanout_default_workers == 3
    assert cfg.ralph.stuck_window == 2
    assert cfg.subprocess.default_timeout_s == 5
    assert cfg.logging.json_fields[0] == "ts"
    assert cfg.edits.hash_prefix_length == 8
    assert cfg.source_path == harness_toml


def test_dataclasses_are_frozen(runtime_cfg: runtime.FullRuntimeConfig) -> None:
    with pytest.raises(FrozenInstanceError):
        runtime_cfg.runtime.max_iterations = 999  # type: ignore[misc]


def test_missing_section_raises(tmp_path: Path) -> None:
    path = tmp_path / "harness.toml"
    path.write_text("[project]\nname = 'x'\n", encoding="utf-8")
    with pytest.raises(runtime.ConfigError):
        runtime.runtime_config_from_harness(path)


def test_missing_key_raises(harness_toml_factory: Callable[..., Path]) -> None:
    path = harness_toml_factory()
    text = path.read_text()
    truncated = text.replace("default_model = \"echo\"", "")
    path.write_text(truncated, encoding="utf-8")
    with pytest.raises(runtime.ConfigError):
        runtime.runtime_config_from_harness(path)


def test_acceptance_tasks_must_be_str_list(harness_toml_factory: Callable[..., Path]) -> None:
    path = harness_toml_factory()
    text = path.read_text().replace(
        'acceptance_tasks = ["lint", "typecheck", "test"]',
        "acceptance_tasks = [1, 2, 3]",
    )
    path.write_text(text, encoding="utf-8")
    with pytest.raises(runtime.ConfigError):
        runtime.runtime_config_from_harness(path)


def test_overrides_take_effect(harness_toml_factory: Callable[..., Path]) -> None:
    path = harness_toml_factory(max_iters=99, ralph_max=7, stuck_action="sleep")
    cfg = runtime.runtime_config_from_harness(path)
    assert cfg.runtime.max_iterations == 99
    assert cfg.ralph.max_iterations == 7
    assert cfg.ralph.stuck_action == "sleep"


def test_default_path_resolves_to_repo_toml() -> None:
    # Importing the module without arguments must point at the repo's harness.toml.
    cfg = runtime.runtime_config_from_harness()
    assert cfg.source_path.name == "harness.toml"
    assert isinstance(cfg.runtime.max_iterations, int)
