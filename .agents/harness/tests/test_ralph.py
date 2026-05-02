from __future__ import annotations

import pytest
import runtime

pytestmark = pytest.mark.unit


def _build(
    *,
    runtime_cfg: runtime.FullRuntimeConfig,
    memory_store: runtime.MemoryStore,
    inner_results: list[runtime.LoopResult],
    acceptance_codes: dict[str, int],
    cfg_overrides: dict[str, object] | None = None,
) -> tuple[runtime.RalphDriver, list[float]]:
    """Construct a RalphDriver with a stubbed inner that returns scripted results."""

    class _Inner:
        def __init__(self) -> None:
            self._cursor = 0

        def run(self, _intent: runtime.Intent) -> runtime.LoopResult:
            r = inner_results[self._cursor]
            if self._cursor + 1 < len(inner_results):
                self._cursor += 1
            return r

    sleeps: list[float] = []

    def sleeper(s: float) -> None:
        sleeps.append(s)

    base = runtime_cfg.ralph
    fields = {
        "max_iterations": base.max_iterations,
        "stuck_window": base.stuck_window,
        "stuck_action": base.stuck_action,
        "sleep_seconds_on_stuck": base.sleep_seconds_on_stuck,
        "require_acceptance_before_signal": base.require_acceptance_before_signal,
        "progress_marker_file": base.progress_marker_file,
    }
    fields.update(cfg_overrides or {})
    cfg = runtime.RalphConfig(**fields)  # type: ignore[arg-type]

    acceptance = runtime.AcceptanceChecker(
        command_runner=lambda name: acceptance_codes.get(name, 0),
    )
    driver = runtime.RalphDriver(
        cfg, inner=_Inner(), acceptance=acceptance, memory=memory_store, sleeper=sleeper,
    )
    return driver, sleeps


def test_accepted_when_inner_and_acceptance_pass(
    runtime_cfg: runtime.FullRuntimeConfig, memory_store: runtime.MemoryStore,
) -> None:
    inner = [
        runtime.LoopResult(
            accepted=True, iterations=1, last_acceptance={"lint": 0},
            correlation_id="c1", transcript=(),
        ),
    ]
    driver, _sleeps = _build(
        runtime_cfg=runtime_cfg, memory_store=memory_store,
        inner_results=inner, acceptance_codes={"lint": 0},
    )
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    report = driver.drive(intent)
    assert report.completed is True
    assert report.reason == "accepted"
    assert report.iterations == 1


def test_max_iterations_hit(
    runtime_cfg: runtime.FullRuntimeConfig, memory_store: runtime.MemoryStore,
) -> None:
    failing = [
        runtime.LoopResult(
            accepted=False, iterations=1, last_acceptance={"lint": 1},
            correlation_id=f"c{i}", transcript=(),
        )
        for i in range(10)
    ]
    driver, _ = _build(
        runtime_cfg=runtime_cfg, memory_store=memory_store,
        inner_results=failing, acceptance_codes={"lint": 1},
        cfg_overrides={"max_iterations": 2, "stuck_window": 5, "stuck_action": "abort"},
    )
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    report = driver.drive(intent)
    assert report.completed is False
    assert report.reason == "max_iterations"
    assert report.iterations == 2


def test_stuck_window_aborts_under_abort_action(
    runtime_cfg: runtime.FullRuntimeConfig, memory_store: runtime.MemoryStore,
) -> None:
    failing = [
        runtime.LoopResult(
            accepted=False, iterations=1, last_acceptance={"lint": 1},
            correlation_id=f"c{i}", transcript=(),
        )
        for i in range(5)
    ]
    driver, _ = _build(
        runtime_cfg=runtime_cfg, memory_store=memory_store,
        inner_results=failing, acceptance_codes={"lint": 1},
        cfg_overrides={"max_iterations": 10, "stuck_window": 2, "stuck_action": "abort"},
    )
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    report = driver.drive(intent)
    assert report.reason == "stuck"
    assert report.completed is False


def test_stuck_action_sleep_resets_window_and_continues(
    runtime_cfg: runtime.FullRuntimeConfig, memory_store: runtime.MemoryStore,
) -> None:
    failing_then_pass = [
        runtime.LoopResult(
            accepted=False, iterations=1, last_acceptance={"lint": 1},
            correlation_id=f"c{i}", transcript=(),
        )
        for i in range(3)
    ] + [
        runtime.LoopResult(
            accepted=True, iterations=1, last_acceptance={"lint": 0},
            correlation_id="c-final", transcript=(),
        ),
    ]
    driver, sleep_ref = _build(
        runtime_cfg=runtime_cfg, memory_store=memory_store,
        inner_results=failing_then_pass, acceptance_codes={"lint": 0},
        cfg_overrides={"max_iterations": 10, "stuck_window": 2, "stuck_action": "sleep"},
    )
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    # Patch acceptance to flip from failing to passing after the sleep.
    driver._acceptance = runtime.AcceptanceChecker(
        command_runner=lambda name: 0,
    )
    report = driver.drive(intent)
    assert report.completed is True
    assert sleep_ref, "sleeper must have been called at least once on stuck"


def test_backpressure_keeps_looping_when_acceptance_fails(
    runtime_cfg: runtime.FullRuntimeConfig, memory_store: runtime.MemoryStore,
) -> None:
    inner = [
        runtime.LoopResult(
            accepted=True, iterations=1, last_acceptance={"lint": 0},
            correlation_id="c1", transcript=(),
        ),
        runtime.LoopResult(
            accepted=True, iterations=1, last_acceptance={"lint": 0},
            correlation_id="c2", transcript=(),
        ),
    ]
    driver, _ = _build(
        runtime_cfg=runtime_cfg, memory_store=memory_store,
        inner_results=inner, acceptance_codes={"lint": 1},
        cfg_overrides={
            "max_iterations": 2,
            "stuck_window": 5,
            "stuck_action": "abort",
            "require_acceptance_before_signal": True,
        },
    )
    intent = runtime.Intent(summary="x", acceptance_tasks=("lint",))
    report = driver.drive(intent)
    assert report.completed is False
    assert report.reason == "max_iterations"


def test_is_stuck_window_logic(
    runtime_cfg: runtime.FullRuntimeConfig, memory_store: runtime.MemoryStore,
) -> None:
    driver, _ = _build(
        runtime_cfg=runtime_cfg, memory_store=memory_store,
        inner_results=[
            runtime.LoopResult(
                accepted=False, iterations=1, last_acceptance={"lint": 1},
                correlation_id="c", transcript=(),
            )
        ],
        acceptance_codes={"lint": 1},
    )
    one = runtime.LoopResult(
        accepted=False, iterations=1, last_acceptance={"lint": 1},
        correlation_id="c", transcript=(),
    )
    two = runtime.LoopResult(
        accepted=False, iterations=1, last_acceptance={"lint": 1},
        correlation_id="c", transcript=(),
    )
    assert driver.is_stuck([one]) is False
    assert driver.is_stuck([one, two]) is True
