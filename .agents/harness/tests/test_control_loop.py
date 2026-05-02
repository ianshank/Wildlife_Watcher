from __future__ import annotations

from collections.abc import Callable, Mapping

import pytest
import runtime

pytestmark = pytest.mark.unit


def _build_loop(
    *,
    cfg: runtime.RuntimeConfig,
    model: runtime.ModelAdapter,
    memory: runtime.MemoryStore,
    acceptance: runtime.AcceptanceChecker,
) -> runtime.ControlLoop:
    return runtime.ControlLoop(
        cfg, model=model, tools=runtime.ToolRegistry(),
        memory=memory, acceptance=acceptance,
    )


def test_happy_path_terminates_on_acceptance(
    runtime_cfg: runtime.FullRuntimeConfig,
    memory_store: runtime.MemoryStore,
    echo_model_factory: Callable[..., runtime.EchoModel],
    acceptance_factory: Callable[..., runtime.AcceptanceChecker],
) -> None:
    model = echo_model_factory(
        [runtime.ModelTurn(rationale="done", tool_calls=(), final=True)],
    )
    acceptance = acceptance_factory({"lint": 0, "typecheck": 0, "test": 0})
    loop = _build_loop(
        cfg=runtime_cfg.runtime, model=model, memory=memory_store, acceptance=acceptance,
    )
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint", "typecheck", "test"))
    result = loop.run(intent)
    assert result.accepted is True
    assert result.iterations == 1
    assert all(code == 0 for code in result.last_acceptance.values())


def test_max_iterations_returns_not_accepted(
    runtime_cfg: runtime.FullRuntimeConfig,
    memory_store: runtime.MemoryStore,
    echo_model_factory: Callable[..., runtime.EchoModel],
    acceptance_factory: Callable[..., runtime.AcceptanceChecker],
) -> None:
    cap = runtime_cfg.runtime.max_iterations
    turns = [
        runtime.ModelTurn(rationale=f"r{i}", tool_calls=(), final=False)
        for i in range(cap)
    ]
    model = echo_model_factory(turns)
    acceptance = acceptance_factory({"lint": 0, "typecheck": 0, "test": 0})
    loop = _build_loop(
        cfg=runtime_cfg.runtime, model=model, memory=memory_store, acceptance=acceptance,
    )
    intent = runtime.Intent(summary="loop", acceptance_tasks=("lint",))
    result = loop.run(intent)
    assert result.accepted is False
    assert result.iterations == cap


def test_loops_until_acceptance_passes(
    runtime_cfg: runtime.FullRuntimeConfig,
    memory_store: runtime.MemoryStore,
    echo_model_factory: Callable[..., runtime.EchoModel],
) -> None:
    state: dict[str, int] = {"calls": 0}

    def runner(name: str) -> int:
        state["calls"] += 1
        return 0 if state["calls"] >= 4 else 1

    acceptance = runtime.AcceptanceChecker(command_runner=runner)
    turns = [runtime.ModelTurn(rationale=f"r{i}", tool_calls=(), final=True) for i in range(5)]
    model = echo_model_factory(turns)
    loop = _build_loop(
        cfg=runtime_cfg.runtime, model=model, memory=memory_store, acceptance=acceptance,
    )
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    result = loop.run(intent)
    assert result.accepted is True
    assert result.iterations >= 4


def test_tool_calls_dispatch(
    runtime_cfg: runtime.FullRuntimeConfig,
    memory_store: runtime.MemoryStore,
    echo_model_factory: Callable[..., runtime.EchoModel],
    acceptance_factory: Callable[..., runtime.AcceptanceChecker],
) -> None:
    invocations: list[Mapping[str, object]] = []

    def record(args: Mapping[str, object]) -> str:
        invocations.append(args)
        return "ok"

    tools = runtime.ToolRegistry()
    tools.register("fs.view", record)

    model = echo_model_factory(
        [
            runtime.ModelTurn(
                rationale="call",
                tool_calls=(runtime.ToolCall(name="fs.view", arguments={"path": "x"}),),
                final=True,
            ),
        ]
    )
    acceptance = acceptance_factory({"lint": 0})
    loop = runtime.ControlLoop(
        runtime_cfg.runtime, model=model, tools=tools,
        memory=memory_store, acceptance=acceptance,
    )
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    result = loop.run(intent)
    assert result.accepted
    assert invocations == [{"path": "x"}]


def test_tool_failure_is_recorded_and_does_not_kill_loop(
    runtime_cfg: runtime.FullRuntimeConfig,
    memory_store: runtime.MemoryStore,
    echo_model_factory: Callable[..., runtime.EchoModel],
    acceptance_factory: Callable[..., runtime.AcceptanceChecker],
) -> None:
    def boom(_args: Mapping[str, object]) -> object:
        raise RuntimeError("nope")

    tools = runtime.ToolRegistry()
    tools.register("bad", boom)
    model = echo_model_factory(
        [
            runtime.ModelTurn(
                rationale="call",
                tool_calls=(runtime.ToolCall(name="bad", arguments={}),),
                final=True,
            ),
        ]
    )
    acceptance = acceptance_factory({"lint": 0})
    loop = runtime.ControlLoop(
        runtime_cfg.runtime, model=model, tools=tools,
        memory=memory_store, acceptance=acceptance,
    )
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    result = loop.run(intent)
    assert result.accepted
    assert any("ERROR" in line for line in result.transcript)


def test_correlation_id_is_stable_within_run(
    runtime_cfg: runtime.FullRuntimeConfig,
    memory_store: runtime.MemoryStore,
    echo_model_factory: Callable[..., runtime.EchoModel],
    acceptance_factory: Callable[..., runtime.AcceptanceChecker],
    correlation_filter: runtime.CorrelationFilter,
) -> None:
    model = echo_model_factory(
        [runtime.ModelTurn(rationale="ok", tool_calls=(), final=True)],
    )
    acceptance = acceptance_factory({"lint": 0})
    loop = runtime.ControlLoop(
        runtime_cfg.runtime, model=model, tools=runtime.ToolRegistry(),
        memory=memory_store, acceptance=acceptance, correlation=correlation_filter,
    )
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    result = loop.run(intent)
    assert result.correlation_id.startswith(runtime_cfg.runtime.correlation_prefix + "-")


def test_tool_registry_rejects_duplicate_registration() -> None:
    tools = runtime.ToolRegistry()
    tools.register("a", lambda _: 1)
    with pytest.raises(KeyError):
        tools.register("a", lambda _: 2)


def test_tool_registry_rejects_unknown_call() -> None:
    tools = runtime.ToolRegistry()
    with pytest.raises(KeyError):
        tools.call("missing", {})
