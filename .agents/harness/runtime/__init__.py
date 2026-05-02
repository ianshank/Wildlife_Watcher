"""Wildlife Watcher agent harness runtime.

Adds a deterministic control loop, persistent Markdown memory, hash-anchored
edits, multi-agent topology composition, and a Ralph driver on top of the
existing task-runner harness in ``.agents/harness/orchestrator.py``.

Public surface kept intentionally small so callers can import a single name
without having to know the underlying module layout.
"""

from __future__ import annotations

from .config import (
    ConfigError,
    EditsConfig,
    FullRuntimeConfig,
    LoggingConfig,
    MemoryConfig,
    RalphConfig,
    RuntimeConfig,
    SubprocessConfig,
    TopologyConfig,
    runtime_config_from_harness,
)
from .control_loop import (
    AcceptanceChecker,
    ControlLoop,
    Intent,
    LoopResult,
    ToolRegistry,
    make_default_turn,
)
from .edits import AnchoredLine, HashAnchoredEditor, HashMismatchError
from .logging_ext import (
    CorrelationFilter,
    JsonFormatter,
    get_runtime_logger,
    install_runtime_logging,
)
from .memory import MemoryStore
from .model_adapter import (
    EchoModel,
    LocalCommandModel,
    ModelAdapter,
    ModelTurn,
    ToolCall,
)
from .ralph import RalphDriver, RalphReport
from .subprocess_safe import SafeRunner, SafeRunResult
from .topology import (
    ExpertPoolTopology,
    FanOutFanInTopology,
    HierarchicalDelegationTopology,
    MapExecutor,
    PipelineTopology,
    ProducerReviewerTopology,
    Reducer,
    SupervisorTopology,
)

__all__ = [
    "AcceptanceChecker",
    "AnchoredLine",
    "ConfigError",
    "ControlLoop",
    "CorrelationFilter",
    "EchoModel",
    "EditsConfig",
    "ExpertPoolTopology",
    "FanOutFanInTopology",
    "FullRuntimeConfig",
    "HashAnchoredEditor",
    "HashMismatchError",
    "HierarchicalDelegationTopology",
    "Intent",
    "JsonFormatter",
    "LocalCommandModel",
    "LoggingConfig",
    "LoopResult",
    "MapExecutor",
    "MemoryConfig",
    "MemoryStore",
    "ModelAdapter",
    "ModelTurn",
    "PipelineTopology",
    "ProducerReviewerTopology",
    "RalphConfig",
    "RalphDriver",
    "RalphReport",
    "Reducer",
    "RuntimeConfig",
    "SafeRunResult",
    "SafeRunner",
    "SubprocessConfig",
    "SupervisorTopology",
    "ToolCall",
    "ToolRegistry",
    "TopologyConfig",
    "get_runtime_logger",
    "install_runtime_logging",
    "make_default_turn",
    "runtime_config_from_harness",
]
