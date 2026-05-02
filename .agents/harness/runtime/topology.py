"""Multi-agent topology composition layer.

Implements six topology patterns from the article over a homogenous
:class:`ControlLoop` interface. Parallel execution uses an injected
``executor_factory`` so tests can plug in a synchronous map executor.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Protocol

from .config import TopologyConfig
from .control_loop import ControlLoop, Intent, LoopResult
from .logging_ext import get_runtime_logger


class Reducer(Protocol):
    def reduce(self, results: Sequence[LoopResult]) -> LoopResult: ...


class _DefaultReducer:
    """Aggregate via short-circuit: if every loop accepted, the bundle accepted."""

    def reduce(self, results: Sequence[LoopResult]) -> LoopResult:
        if not results:
            raise ValueError("Cannot reduce an empty result sequence")
        accepted = all(r.accepted for r in results)
        merged_acceptance: dict[str, int] = {}
        for r in results:
            for task, code in r.last_acceptance.items():
                merged_acceptance[task] = max(merged_acceptance.get(task, 0), code)
        transcript = tuple(line for r in results for line in r.transcript)
        return LoopResult(
            accepted=accepted,
            iterations=sum(r.iterations for r in results),
            last_acceptance=merged_acceptance,
            correlation_id=results[0].correlation_id,
            transcript=transcript,
        )


@dataclass(frozen=True)
class TopologyContext:
    cfg: TopologyConfig
    reducer: Reducer
    logger: logging.Logger


ExecutorFactory = Callable[[int], "_ExecutorLike"]


class _ExecutorLike(Protocol):
    def map(
        self,
        fn: Callable[[ControlLoop], LoopResult],
        loops: Iterable[ControlLoop],
    ) -> Iterable[LoopResult]: ...

    def __enter__(self) -> _ExecutorLike: ...
    def __exit__(self, *exc: object) -> None: ...


class MapExecutor:
    """Synchronous executor used by tests; mirrors the ``map`` interface."""

    def __init__(self, _max_workers: int = 1) -> None:
        self._max = _max_workers

    def map(
        self,
        fn: Callable[[ControlLoop], LoopResult],
        loops: Iterable[ControlLoop],
    ) -> Iterable[LoopResult]:
        return [fn(loop) for loop in loops]

    def __enter__(self) -> MapExecutor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _thread_pool_factory(max_workers: int) -> _ExecutorLike:
    return ThreadPoolExecutor(max_workers=max_workers)  # type: ignore[return-value]


class _BaseTopology:
    name: str = "base"

    def __init__(
        self,
        loops: Sequence[ControlLoop],
        *,
        cfg: TopologyConfig,
        reducer: Reducer | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if not loops:
            raise ValueError(f"Topology '{self.name}' requires at least one loop")
        self._loops = list(loops)
        self._ctx = TopologyContext(
            cfg=cfg,
            reducer=reducer or _DefaultReducer(),
            logger=logger or get_runtime_logger(f"topology.{self.name}"),
        )

    def run(self, intent: Intent) -> Sequence[LoopResult]:  # pragma: no cover
        raise NotImplementedError(
            f"Topology subclass '{type(self).__name__}' must implement run()"
        )


class PipelineTopology(_BaseTopology):
    name = "pipeline"

    def run(self, intent: Intent) -> Sequence[LoopResult]:
        results: list[LoopResult] = []
        running_intent = intent
        for index, loop in enumerate(self._loops):
            self._ctx.logger.info("pipeline.stage index=%d", index)
            result = loop.run(running_intent)
            results.append(result)
            extra = dict(running_intent.extra_context)
            extra[f"stage_{index}_summary"] = " | ".join(result.transcript[-3:])
            running_intent = Intent(
                summary=running_intent.summary,
                acceptance_tasks=running_intent.acceptance_tasks,
                extra_context=extra,
            )
            if not result.accepted:
                self._ctx.logger.info("pipeline.stop index=%d not_accepted", index)
                break
        return results


class FanOutFanInTopology(_BaseTopology):
    name = "fanout"

    def __init__(
        self,
        loops: Sequence[ControlLoop],
        *,
        cfg: TopologyConfig,
        reducer: Reducer | None = None,
        executor_factory: ExecutorFactory = _thread_pool_factory,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(loops, cfg=cfg, reducer=reducer, logger=logger)
        self._executor_factory = executor_factory

    def run(self, intent: Intent) -> Sequence[LoopResult]:
        workers = max(1, min(len(self._loops), self._ctx.cfg.fanout_default_workers))
        self._ctx.logger.info("fanout.start workers=%d", workers)
        with self._executor_factory(workers) as ex:
            results = list(ex.map(lambda loop: loop.run(intent), self._loops))
        merged = self._ctx.reducer.reduce(results)
        self._ctx.logger.info("fanout.done accepted=%s", merged.accepted)
        return [*results, merged]


class ExpertPoolTopology(_BaseTopology):
    name = "expert_pool"

    def __init__(
        self,
        loops: Sequence[ControlLoop],
        *,
        cfg: TopologyConfig,
        router: Callable[[Intent, Sequence[ControlLoop]], Sequence[ControlLoop]] | None = None,
        reducer: Reducer | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(loops, cfg=cfg, reducer=reducer, logger=logger)
        self._router = router or (lambda _intent, ls: ls)

    def run(self, intent: Intent) -> Sequence[LoopResult]:
        chosen = list(self._router(intent, self._loops))
        if len(chosen) < self._ctx.cfg.expert_pool_min_quorum:
            raise ValueError(
                f"expert_pool quorum unmet: chosen={len(chosen)} "
                f"min={self._ctx.cfg.expert_pool_min_quorum}"
            )
        self._ctx.logger.info("expert_pool.quorum=%d", len(chosen))
        results = [loop.run(intent) for loop in chosen]
        return [*results, self._ctx.reducer.reduce(results)]


class ProducerReviewerTopology(_BaseTopology):
    name = "producer_reviewer"

    def __init__(
        self,
        producer: ControlLoop,
        reviewer: ControlLoop,
        *,
        cfg: TopologyConfig,
        reducer: Reducer | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__([producer, reviewer], cfg=cfg, reducer=reducer, logger=logger)
        self._producer = producer
        self._reviewer = reviewer

    def run(self, intent: Intent) -> Sequence[LoopResult]:
        history: list[LoopResult] = []
        for round_index in range(1, self._ctx.cfg.producer_reviewer_max_rounds + 1):
            produced = self._producer.run(intent)
            review_intent = Intent(
                summary=intent.summary,
                acceptance_tasks=intent.acceptance_tasks,
                extra_context={
                    **dict(intent.extra_context),
                    f"round_{round_index}_producer": " | ".join(produced.transcript[-3:]),
                },
            )
            reviewed = self._reviewer.run(review_intent)
            history.extend([produced, reviewed])
            self._ctx.logger.info(
                "producer_reviewer.round=%d producer=%s reviewer=%s",
                round_index, produced.accepted, reviewed.accepted,
            )
            if produced.accepted and reviewed.accepted:
                break
        return history


class SupervisorTopology(_BaseTopology):
    name = "supervisor"

    def __init__(
        self,
        workers: Sequence[ControlLoop],
        *,
        cfg: TopologyConfig,
        reducer: Reducer | None = None,
        escalation_handler: Callable[[Sequence[LoopResult]], LoopResult] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(workers, cfg=cfg, reducer=reducer, logger=logger)
        self._workers = list(workers)
        self._escalation = escalation_handler

    def run(self, intent: Intent) -> Sequence[LoopResult]:
        results: list[LoopResult] = []
        failures = 0
        for worker in self._workers:
            outcome = worker.run(intent)
            results.append(outcome)
            if not outcome.accepted:
                failures += 1
                self._ctx.logger.warning("supervisor.failure count=%d", failures)
                if failures >= self._ctx.cfg.supervisor_escalation_threshold:
                    if self._escalation is None:
                        self._ctx.logger.error("supervisor.escalate no_handler")
                        break
                    escalated = self._escalation(results)
                    results.append(escalated)
                    break
        return results


class HierarchicalDelegationTopology(_BaseTopology):
    name = "hierarchical"

    def __init__(
        self,
        manager: ControlLoop,
        sub_managers: Mapping[str, HierarchicalDelegationTopology | _BaseTopology],
        *,
        cfg: TopologyConfig,
        reducer: Reducer | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__([manager], cfg=cfg, reducer=reducer, logger=logger)
        self._manager = manager
        self._subs = dict(sub_managers)

    def run(self, intent: Intent) -> Sequence[LoopResult]:
        plan = self._manager.run(intent)
        aggregated: list[LoopResult] = [plan]
        child_results: list[LoopResult] = []
        for label, sub in self._subs.items():
            sub_results = list(sub.run(intent))
            self._ctx.logger.info(
                "hierarchical.sub label=%s count=%d", label, len(sub_results),
            )
            child_results.extend(sub_results)
        if child_results:
            aggregated.append(self._ctx.reducer.reduce(child_results))
        return aggregated
