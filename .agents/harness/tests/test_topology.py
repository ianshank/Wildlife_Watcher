from __future__ import annotations

from collections.abc import Sequence

import pytest
import runtime

pytestmark = pytest.mark.unit


def _loop(
    runtime_cfg: runtime.FullRuntimeConfig,
    memory_store: runtime.MemoryStore,
    *,
    final: bool = True,
    accept_codes: dict[str, int] | None = None,
    turn_budget: int | None = None,
) -> runtime.ControlLoop:
    codes = accept_codes if accept_codes is not None else {"lint": 0, "typecheck": 0, "test": 0}
    # Provide enough turns so the inner loop can spin up to its iteration cap
    # if acceptance keeps failing, and so a single loop reused across rounds
    # (e.g., producer-reviewer) does not exhaust its script.
    budget = turn_budget if turn_budget is not None else runtime_cfg.runtime.max_iterations
    turns = [
        runtime.ModelTurn(rationale=f"r{i}", tool_calls=(), final=final)
        for i in range(budget)
    ]
    model = runtime.EchoModel(script=turns)
    acceptance = runtime.AcceptanceChecker(command_runner=lambda name: codes.get(name, 0))
    return runtime.ControlLoop(
        runtime_cfg.runtime, model=model, tools=runtime.ToolRegistry(),
        memory=memory_store, acceptance=acceptance,
    )


def test_pipeline_runs_stages_in_order(
    runtime_cfg: runtime.FullRuntimeConfig, memory_store: runtime.MemoryStore,
) -> None:
    loops = [_loop(runtime_cfg, memory_store) for _ in range(3)]
    pipeline = runtime.PipelineTopology(loops, cfg=runtime_cfg.topology)
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    results = pipeline.run(intent)
    assert len(results) == 3
    assert all(r.accepted for r in results)


def test_pipeline_stops_on_failure(
    runtime_cfg: runtime.FullRuntimeConfig, memory_store: runtime.MemoryStore,
) -> None:
    good = _loop(runtime_cfg, memory_store)
    bad = _loop(runtime_cfg, memory_store, accept_codes={"lint": 1})
    last = _loop(runtime_cfg, memory_store)
    pipeline = runtime.PipelineTopology([good, bad, last], cfg=runtime_cfg.topology)
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    results = pipeline.run(intent)
    assert len(results) == 2
    assert results[0].accepted and not results[1].accepted


def test_fanout_uses_synchronous_executor(
    runtime_cfg: runtime.FullRuntimeConfig, memory_store: runtime.MemoryStore,
) -> None:
    loops = [_loop(runtime_cfg, memory_store) for _ in range(3)]
    topology = runtime.FanOutFanInTopology(
        loops,
        cfg=runtime_cfg.topology,
        executor_factory=lambda n: runtime.MapExecutor(n),
    )
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    results = topology.run(intent)
    # Last entry is the reducer's merged result.
    merged = results[-1]
    assert merged.accepted is True
    assert len(results) == len(loops) + 1


def test_fanout_reducer_short_circuits_on_any_failure(
    runtime_cfg: runtime.FullRuntimeConfig, memory_store: runtime.MemoryStore,
) -> None:
    a = _loop(runtime_cfg, memory_store)
    b = _loop(runtime_cfg, memory_store, accept_codes={"lint": 1})
    topology = runtime.FanOutFanInTopology(
        [a, b],
        cfg=runtime_cfg.topology,
        executor_factory=lambda n: runtime.MapExecutor(n),
    )
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    merged = topology.run(intent)[-1]
    assert merged.accepted is False


def test_expert_pool_quorum_enforced(
    runtime_cfg: runtime.FullRuntimeConfig, memory_store: runtime.MemoryStore,
) -> None:
    loops = [_loop(runtime_cfg, memory_store)]
    topology = runtime.ExpertPoolTopology(
        loops,
        cfg=runtime_cfg.topology,
        router=lambda _intent, ls: ls,
    )
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    with pytest.raises(ValueError):
        topology.run(intent)


def test_expert_pool_runs_quorum(
    runtime_cfg: runtime.FullRuntimeConfig, memory_store: runtime.MemoryStore,
) -> None:
    loops = [_loop(runtime_cfg, memory_store) for _ in range(3)]
    topology = runtime.ExpertPoolTopology(loops, cfg=runtime_cfg.topology)
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    results = topology.run(intent)
    assert len(results) == 4  # 3 + reducer


def test_producer_reviewer_iterates_until_accept(
    runtime_cfg: runtime.FullRuntimeConfig, memory_store: runtime.MemoryStore,
) -> None:
    producer = _loop(runtime_cfg, memory_store)
    reviewer = _loop(runtime_cfg, memory_store)
    topology = runtime.ProducerReviewerTopology(
        producer=producer, reviewer=reviewer, cfg=runtime_cfg.topology,
    )
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    results = topology.run(intent)
    # First round both pass -> exits after 2 results.
    assert len(results) == 2
    assert all(r.accepted for r in results)


def test_producer_reviewer_respects_max_rounds(
    runtime_cfg: runtime.FullRuntimeConfig, memory_store: runtime.MemoryStore,
) -> None:
    rounds = runtime_cfg.topology.producer_reviewer_max_rounds
    iters = runtime_cfg.runtime.max_iterations
    # The same loop is reused for every round, so the model needs enough
    # turns to cover (rounds * inner iterations).
    failing = _loop(
        runtime_cfg, memory_store, accept_codes={"lint": 1},
        turn_budget=rounds * iters,
    )
    passing = _loop(runtime_cfg, memory_store, turn_budget=rounds * iters)
    topology = runtime.ProducerReviewerTopology(
        producer=failing, reviewer=passing, cfg=runtime_cfg.topology,
    )
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    results = topology.run(intent)
    assert len(results) == rounds * 2


def test_supervisor_escalates_on_threshold(
    runtime_cfg: runtime.FullRuntimeConfig, memory_store: runtime.MemoryStore,
) -> None:
    failing_workers = [
        _loop(runtime_cfg, memory_store, accept_codes={"lint": 1}) for _ in range(3)
    ]
    escalated_seen: list[Sequence[runtime.LoopResult]] = []

    def handler(results: Sequence[runtime.LoopResult]) -> runtime.LoopResult:
        escalated_seen.append(results)
        return runtime.LoopResult(
            accepted=False, iterations=0, last_acceptance={"lint": 9},
            correlation_id="esc", transcript=("escalated",),
        )

    topology = runtime.SupervisorTopology(
        failing_workers,
        cfg=runtime_cfg.topology,
        escalation_handler=handler,
    )
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    results = topology.run(intent)
    assert escalated_seen, "escalation handler should have fired"
    assert results[-1].correlation_id == "esc"


def test_hierarchical_aggregates_children(
    runtime_cfg: runtime.FullRuntimeConfig, memory_store: runtime.MemoryStore,
) -> None:
    manager = _loop(runtime_cfg, memory_store)
    sub_a = runtime.PipelineTopology(
        [_loop(runtime_cfg, memory_store) for _ in range(2)], cfg=runtime_cfg.topology,
    )
    sub_b = runtime.PipelineTopology(
        [_loop(runtime_cfg, memory_store)], cfg=runtime_cfg.topology,
    )
    tree = runtime.HierarchicalDelegationTopology(
        manager,
        sub_managers={"a": sub_a, "b": sub_b},
        cfg=runtime_cfg.topology,
    )
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    results = tree.run(intent)
    # 1 manager + 1 reducer for child results.
    assert len(results) == 2
