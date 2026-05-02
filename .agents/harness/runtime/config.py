"""Frozen, typed configuration for the agent harness runtime.

Every default value lives in ``.agents/harness.toml``. This module reads that
file once and produces immutable dataclasses; it never falls back to Python
literals so callers cannot accidentally diverge from the on-disk source of
truth.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - 3.10 fallback
    import tomli as tomllib

LOGGER = logging.getLogger("wildlife_harness.runtime.config")

DEFAULT_HARNESS_TOML = (
    Path(__file__).resolve().parents[2] / "harness.toml"
)


class ConfigError(ValueError):
    """Raised when a required section or key is missing from harness.toml."""


@dataclass(frozen=True)
class RuntimeConfig:
    default_model: str
    acceptance_tasks: tuple[str, ...]
    max_iterations: int
    iteration_timeout_s: float
    correlation_prefix: str


@dataclass(frozen=True)
class MemoryConfig:
    root: str
    index_file: str
    episodic_dir: str
    spec_dir: str
    rotate_after_bytes: int
    rotate_keep_tail_bytes: int
    gc_heartbeat_iterations: int
    atomic_write_suffix: str


@dataclass(frozen=True)
class TopologyConfig:
    pipeline_default_stages: tuple[str, ...]
    fanout_default_workers: int
    expert_pool_min_quorum: int
    producer_reviewer_max_rounds: int
    supervisor_escalation_threshold: int


@dataclass(frozen=True)
class RalphConfig:
    max_iterations: int
    stuck_window: int
    stuck_action: str
    sleep_seconds_on_stuck: float
    require_acceptance_before_signal: bool
    progress_marker_file: str


@dataclass(frozen=True)
class SubprocessConfig:
    default_timeout_s: float
    truncate_head_bytes: int
    truncate_tail_bytes: int
    spill_dir: str
    spill_threshold_bytes: int
    env_allowlist: tuple[str, ...]
    env_denylist_substrings: tuple[str, ...]


@dataclass(frozen=True)
class LoggingConfig:
    json_fields: tuple[str, ...]


@dataclass(frozen=True)
class EditsConfig:
    hash_algo: str
    hash_prefix_length: int
    mismatch_behavior: str


@dataclass(frozen=True)
class FullRuntimeConfig:
    runtime: RuntimeConfig
    memory: MemoryConfig
    topology: TopologyConfig
    ralph: RalphConfig
    subprocess: SubprocessConfig
    logging: LoggingConfig
    edits: EditsConfig
    source_path: Path


def _require(section: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in section:
        raise ConfigError(f"Missing key '{key}' in [{where}] of harness.toml")
    return section[key]


def _str_tuple(values: Any, where: str) -> tuple[str, ...]:
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise ConfigError(f"[{where}] must be a list[str]")
    return tuple(values)


def _section(raw: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    if name not in raw:
        raise ConfigError(f"Missing section [{name}] in harness.toml")
    section = raw[name]
    if not isinstance(section, dict):
        raise ConfigError(f"Section [{name}] must be a table")
    return section


def _build_runtime(section: Mapping[str, Any]) -> RuntimeConfig:
    return RuntimeConfig(
        default_model=str(_require(section, "default_model", "runtime")),
        acceptance_tasks=_str_tuple(
            _require(section, "acceptance_tasks", "runtime"),
            "runtime.acceptance_tasks",
        ),
        max_iterations=int(_require(section, "max_iterations", "runtime")),
        iteration_timeout_s=float(_require(section, "iteration_timeout_s", "runtime")),
        correlation_prefix=str(_require(section, "correlation_prefix", "runtime")),
    )


def _build_memory(section: Mapping[str, Any]) -> MemoryConfig:
    return MemoryConfig(
        root=str(_require(section, "root", "memory")),
        index_file=str(_require(section, "index_file", "memory")),
        episodic_dir=str(_require(section, "episodic_dir", "memory")),
        spec_dir=str(_require(section, "spec_dir", "memory")),
        rotate_after_bytes=int(_require(section, "rotate_after_bytes", "memory")),
        rotate_keep_tail_bytes=int(_require(section, "rotate_keep_tail_bytes", "memory")),
        gc_heartbeat_iterations=int(_require(section, "gc_heartbeat_iterations", "memory")),
        atomic_write_suffix=str(_require(section, "atomic_write_suffix", "memory")),
    )


def _build_topology(section: Mapping[str, Any]) -> TopologyConfig:
    return TopologyConfig(
        pipeline_default_stages=_str_tuple(
            _require(section, "pipeline_default_stages", "topology"),
            "topology.pipeline_default_stages",
        ),
        fanout_default_workers=int(_require(section, "fanout_default_workers", "topology")),
        expert_pool_min_quorum=int(_require(section, "expert_pool_min_quorum", "topology")),
        producer_reviewer_max_rounds=int(
            _require(section, "producer_reviewer_max_rounds", "topology")
        ),
        supervisor_escalation_threshold=int(
            _require(section, "supervisor_escalation_threshold", "topology")
        ),
    )


def _build_ralph(section: Mapping[str, Any]) -> RalphConfig:
    return RalphConfig(
        max_iterations=int(_require(section, "max_iterations", "ralph")),
        stuck_window=int(_require(section, "stuck_window", "ralph")),
        stuck_action=str(_require(section, "stuck_action", "ralph")),
        sleep_seconds_on_stuck=float(_require(section, "sleep_seconds_on_stuck", "ralph")),
        require_acceptance_before_signal=bool(
            _require(section, "require_acceptance_before_signal", "ralph")
        ),
        progress_marker_file=str(_require(section, "progress_marker_file", "ralph")),
    )


def _build_subprocess(section: Mapping[str, Any]) -> SubprocessConfig:
    return SubprocessConfig(
        default_timeout_s=float(_require(section, "default_timeout_s", "subprocess")),
        truncate_head_bytes=int(_require(section, "truncate_head_bytes", "subprocess")),
        truncate_tail_bytes=int(_require(section, "truncate_tail_bytes", "subprocess")),
        spill_dir=str(_require(section, "spill_dir", "subprocess")),
        spill_threshold_bytes=int(_require(section, "spill_threshold_bytes", "subprocess")),
        env_allowlist=_str_tuple(
            _require(section, "env_allowlist", "subprocess"),
            "subprocess.env_allowlist",
        ),
        env_denylist_substrings=_str_tuple(
            _require(section, "env_denylist_substrings", "subprocess"),
            "subprocess.env_denylist_substrings",
        ),
    )


def _build_logging(section: Mapping[str, Any]) -> LoggingConfig:
    return LoggingConfig(
        json_fields=_str_tuple(
            _require(section, "json_fields", "logging"),
            "logging.json_fields",
        ),
    )


def _build_edits(section: Mapping[str, Any]) -> EditsConfig:
    return EditsConfig(
        hash_algo=str(_require(section, "hash_algo", "edits")),
        hash_prefix_length=int(_require(section, "hash_prefix_length", "edits")),
        mismatch_behavior=str(_require(section, "mismatch_behavior", "edits")),
    )


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        data: dict[str, Any] = tomllib.load(handle)
    return data


def runtime_config_from_harness(harness_path: Path | None = None) -> FullRuntimeConfig:
    path = harness_path or DEFAULT_HARNESS_TOML
    raw = _load_toml(path)
    LOGGER.debug("Loaded harness config from %s (sections=%s)", path, sorted(raw.keys()))
    return FullRuntimeConfig(
        runtime=_build_runtime(_section(raw, "runtime")),
        memory=_build_memory(_section(raw, "memory")),
        topology=_build_topology(_section(raw, "topology")),
        ralph=_build_ralph(_section(raw, "ralph")),
        subprocess=_build_subprocess(_section(raw, "subprocess")),
        logging=_build_logging(_section(raw, "logging")),
        edits=_build_edits(_section(raw, "edits")),
        source_path=path,
    )
