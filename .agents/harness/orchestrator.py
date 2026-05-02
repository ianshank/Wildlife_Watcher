from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Make the local ``runtime`` package importable regardless of whether this
# script is executed directly (``python .agents/harness/orchestrator.py``) or
# via ``python -m`` from a package mount. The directory containing this file
# is the parent of the ``runtime`` package; adding it to ``sys.path`` makes
# ``from runtime import ...`` work in both invocation modes without ever
# attempting a relative import that requires a parent package context.
_HARNESS_DIR = Path(__file__).resolve().parent
if str(_HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(_HARNESS_DIR))

import paho.mqtt.publish as mqtt_publish  # noqa: E402 - sys.path bootstrap above
import yaml  # noqa: E402

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_CONFIG_PATH = REPO_ROOT / ".agents" / "harness.toml"
DEFAULT_WILDLIFE_CONFIG = Path("pi-display-node/kiosk/test_config.yaml")
LOGGER = logging.getLogger("wildlife_harness")

TaskHandler = Callable[[argparse.Namespace, "HarnessContext"], int]
TASKS: dict[str, TaskHandler] = {}


@dataclass(frozen=True)
class HarnessConfig:
    repo_root: Path
    wildlife_config: Path
    pythonpath: list[Path]
    commands: dict[str, list[str]]
    required_agent_paths: list[Path]
    ignored_names: set[str]


@dataclass(frozen=True)
class HarnessContext:
    config: HarnessConfig


def register_task(name: str) -> Callable[[TaskHandler], TaskHandler]:
    def decorator(func: TaskHandler) -> TaskHandler:
        TASKS[name] = func
        return func

    return decorator


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        data: dict[str, Any] = tomllib.load(handle)
    return data


def load_config() -> HarnessConfig:
    raw = _load_toml(HARNESS_CONFIG_PATH)
    tokens = {
        "python": sys.executable,
        "repo_root": str(REPO_ROOT),
    }
    project = raw.get("project", {})
    wildlife_config = REPO_ROOT / Path(project.get("wildlife_config", str(DEFAULT_WILDLIFE_CONFIG)))
    pythonpath = [REPO_ROOT / Path(entry) for entry in project.get("pythonpath", [])]
    commands = {
        name: [part.format_map(tokens) for part in parts]
        for name, parts in raw.get("commands", {}).items()
    }
    agent_docs = raw.get("agent_docs", {})
    required_agent_paths = [REPO_ROOT / Path(path) for path in agent_docs.get("required_paths", [])]
    ignored_names = set(agent_docs.get("ignore_names", []))
    return HarnessConfig(
        repo_root=REPO_ROOT,
        wildlife_config=wildlife_config,
        pythonpath=pythonpath,
        commands=commands,
        required_agent_paths=required_agent_paths,
        ignored_names=ignored_names,
    )


def run_command(command: list[str], context: HarnessContext, dry_run: bool) -> int:
    LOGGER.info("Running: %s", " ".join(command))
    if dry_run:
        return 0
    environment = os.environ.copy()
    pythonpath_entries = [str(path) for path in context.config.pythonpath]
    existing_pythonpath = environment.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_entries.append(existing_pythonpath)
    if pythonpath_entries:
        environment["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    completed = subprocess.run(command, cwd=REPO_ROOT, env=environment, check=False)
    return completed.returncode


def run_named_command(name: str, context: HarnessContext, dry_run: bool) -> int:
    command = context.config.commands.get(name)
    if command is None:
        raise KeyError(f"Unknown harness command: {name}")
    return run_command(command, context, dry_run)


def load_wildlife_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError(f"Wildlife config at {path} must be a mapping")
    return raw


def topic_from_pattern(pattern: str, node_id: str) -> str:
    if "+" in pattern:
        return pattern.replace("+", node_id, 1)
    return f"{pattern.rstrip('/')}/{node_id}"


@register_task("lint")
def task_lint(args: argparse.Namespace, context: HarnessContext) -> int:
    return run_named_command("lint", context, args.dry_run)


@register_task("typecheck")
def task_typecheck(args: argparse.Namespace, context: HarnessContext) -> int:
    return run_named_command("typecheck", context, args.dry_run)


@register_task("test")
def task_test(args: argparse.Namespace, context: HarnessContext) -> int:
    return run_named_command("test", context, args.dry_run)


@register_task("quality")
def task_quality(args: argparse.Namespace, context: HarnessContext) -> int:
    for name in ("lint", "typecheck", "test"):
        exit_code = run_named_command(name, context, args.dry_run)
        if exit_code != 0:
            return exit_code
    return 0


@register_task("firmware-build")
def task_firmware_build(args: argparse.Namespace, context: HarnessContext) -> int:
    return run_named_command("firmware-build", context, args.dry_run)


@register_task("firmware-build-phase2")
def task_firmware_build_phase2(args: argparse.Namespace, context: HarnessContext) -> int:
    return run_named_command("firmware-build-phase2", context, args.dry_run)


@register_task("firmware-test-native")
def task_firmware_test_native(args: argparse.Namespace, context: HarnessContext) -> int:
    return run_named_command("firmware-test-native", context, args.dry_run)


@register_task("ml-pipeline-typecheck")
def task_ml_pipeline_typecheck(args: argparse.Namespace, context: HarnessContext) -> int:
    return run_named_command("ml-pipeline-typecheck", context, args.dry_run)


@register_task("ml-pipeline-lint")
def task_ml_pipeline_lint(args: argparse.Namespace, context: HarnessContext) -> int:
    return run_named_command("ml-pipeline-lint", context, args.dry_run)


@register_task("ml-pipeline-test")
def task_ml_pipeline_test(args: argparse.Namespace, context: HarnessContext) -> int:
    return run_named_command("ml-pipeline-test", context, args.dry_run)


@register_task("ml-pipeline-smoke")
def task_ml_pipeline_smoke(args: argparse.Namespace, context: HarnessContext) -> int:
    return run_named_command("ml-pipeline-smoke", context, args.dry_run)


@register_task("agents-md-coverage")
def task_agents_md_coverage(args: argparse.Namespace, context: HarnessContext) -> int:
    missing = [
        path
        for path in context.config.required_agent_paths
        if not (path / "AGENTS.md").exists()
    ]
    if missing:
        for path in missing:
            LOGGER.error("Missing AGENTS.md in %s", path.relative_to(context.config.repo_root))
        return 1
    LOGGER.info("All required directories have AGENTS.md files.")
    return 0


@register_task("runtime-lint")
def task_runtime_lint(args: argparse.Namespace, context: HarnessContext) -> int:
    return run_named_command("runtime-lint", context, args.dry_run)


@register_task("runtime-typecheck")
def task_runtime_typecheck(args: argparse.Namespace, context: HarnessContext) -> int:
    return run_named_command("runtime-typecheck", context, args.dry_run)


@register_task("runtime-test")
def task_runtime_test(args: argparse.Namespace, context: HarnessContext) -> int:
    return run_named_command("runtime-test", context, args.dry_run)


@register_task("quality-runtime")
def task_quality_runtime(args: argparse.Namespace, context: HarnessContext) -> int:
    for name in ("runtime-lint", "runtime-typecheck", "runtime-test"):
        exit_code = run_named_command(name, context, args.dry_run)
        if exit_code != 0:
            return exit_code
    return 0


def _build_runtime_loop(
    args: argparse.Namespace,
    context: HarnessContext,
) -> tuple[Any, Any, Any]:
    """Construct a ``(ControlLoop, Intent, FullRuntimeConfig)`` from CLI + TOML.

    Imports are lazy so legacy task startup is unaffected.
    """

    from runtime import (
        AcceptanceChecker,
        ControlLoop,
        EchoModel,
        Intent,
        MemoryStore,
        ModelTurn,
        ToolRegistry,
        install_runtime_logging,
        runtime_config_from_harness,
    )

    full_cfg = runtime_config_from_harness()
    install_runtime_logging(
        full_cfg.logging,
        correlation_prefix=full_cfg.runtime.correlation_prefix,
    )
    memory_root = context.config.repo_root / full_cfg.memory.root
    memory = MemoryStore(full_cfg.memory, root=memory_root)
    acceptance = AcceptanceChecker(
        command_runner=lambda name: run_named_command(name, context, args.dry_run),
    )
    if args.dry_run:
        scripted = ModelTurn(rationale="dry-run", tool_calls=(), final=True)
    else:
        scripted = ModelTurn(rationale="echo-noop", tool_calls=(), final=True)
    model = EchoModel(script=[scripted])
    tools = ToolRegistry()
    cfg = full_cfg.runtime
    if args.max_iterations is not None:
        cfg = type(cfg)(
            default_model=cfg.default_model,
            acceptance_tasks=cfg.acceptance_tasks,
            max_iterations=int(args.max_iterations),
            iteration_timeout_s=cfg.iteration_timeout_s,
            correlation_prefix=cfg.correlation_prefix,
        )
    loop = ControlLoop(
        cfg, model=model, tools=tools, memory=memory, acceptance=acceptance,
    )
    summary = args.intent or "noop"
    intent = Intent(summary=summary, acceptance_tasks=cfg.acceptance_tasks)
    return loop, intent, full_cfg


@register_task("runtime-loop")
def task_runtime_loop(args: argparse.Namespace, context: HarnessContext) -> int:
    loop, intent, _ = _build_runtime_loop(args, context)
    result = loop.run(intent)
    LOGGER.info(
        "runtime-loop accepted=%s iterations=%d cid=%s",
        result.accepted, result.iterations, result.correlation_id,
    )
    return 0 if result.accepted else 1


@register_task("ralph-run")
def task_ralph_run(args: argparse.Namespace, context: HarnessContext) -> int:
    from runtime import RalphDriver

    loop, intent, full_cfg = _build_runtime_loop(args, context)
    ralph_cfg = full_cfg.ralph
    if args.max_iterations is not None:
        ralph_cfg = type(ralph_cfg)(
            max_iterations=int(args.max_iterations),
            stuck_window=ralph_cfg.stuck_window,
            stuck_action=ralph_cfg.stuck_action,
            sleep_seconds_on_stuck=ralph_cfg.sleep_seconds_on_stuck,
            require_acceptance_before_signal=ralph_cfg.require_acceptance_before_signal,
            progress_marker_file=ralph_cfg.progress_marker_file,
        )
    from runtime import (
        AcceptanceChecker,
        MemoryStore,
        runtime_config_from_harness,
    )

    full_cfg2 = runtime_config_from_harness()
    memory = MemoryStore(
        full_cfg2.memory,
        root=context.config.repo_root / full_cfg2.memory.root,
    )
    acceptance = AcceptanceChecker(
        command_runner=lambda name: run_named_command(name, context, args.dry_run),
    )
    driver = RalphDriver(ralph_cfg, inner=loop, acceptance=acceptance, memory=memory)
    report = driver.drive(intent)
    LOGGER.info(
        "ralph-run completed=%s reason=%s iterations=%d",
        report.completed, report.reason, report.iterations,
    )
    return 0 if report.completed else 1


@register_task("memory-rotate")
def task_memory_rotate(args: argparse.Namespace, context: HarnessContext) -> int:
    from runtime import MemoryStore, runtime_config_from_harness

    cfg = runtime_config_from_harness()
    store = MemoryStore(
        cfg.memory, root=context.config.repo_root / cfg.memory.root,
    )
    archive = store.rotate_index()
    LOGGER.info("memory-rotate archive=%s", archive)
    return 0


@register_task("memory-index")
def task_memory_index(args: argparse.Namespace, context: HarnessContext) -> int:
    from runtime import MemoryStore, runtime_config_from_harness

    cfg = runtime_config_from_harness()
    store = MemoryStore(
        cfg.memory, root=context.config.repo_root / cfg.memory.root,
    )
    index = store.index_path
    if index.exists():
        sys.stdout.write(index.read_text(encoding="utf-8"))
    else:
        LOGGER.warning("memory-index missing path=%s", index)
        return 1
    return 0


@register_task("spec-shard")
def task_spec_shard(args: argparse.Namespace, context: HarnessContext) -> int:
    from runtime import MemoryStore, runtime_config_from_harness

    cfg = runtime_config_from_harness()
    store = MemoryStore(
        cfg.memory, root=context.config.repo_root / cfg.memory.root,
    )
    if not args.shard_id:
        LOGGER.error("spec-shard requires --shard-id")
        return 2
    spec = (
        args.shard_spec
        or "# SPEC\n\nGoals, acceptance criteria, and constraints go here.\n"
    )
    task_md = (
        args.shard_task
        or "# Task\n\n- [ ] First atomic task\n- [ ] Second atomic task\n"
    )
    learnings = args.shard_learnings or "# Learnings\n"
    shard_dir = store.write_spec_shard(args.shard_id, spec, task_md, learnings)
    LOGGER.info("spec-shard dir=%s", shard_dir)
    return 0


def _build_topology_loops(
    args: argparse.Namespace,
    context: HarnessContext,
    count: int,
) -> tuple[list[Any], Any, Any]:
    from runtime import (
        AcceptanceChecker,
        ControlLoop,
        EchoModel,
        Intent,
        MemoryStore,
        ModelTurn,
        ToolRegistry,
        runtime_config_from_harness,
    )

    full_cfg = runtime_config_from_harness()
    memory = MemoryStore(
        full_cfg.memory, root=context.config.repo_root / full_cfg.memory.root,
    )
    acceptance = AcceptanceChecker(
        command_runner=lambda name: run_named_command(name, context, args.dry_run),
    )
    loops: list[Any] = []
    for _ in range(count):
        model = EchoModel(
            script=[ModelTurn(rationale="echo", tool_calls=(), final=True)],
        )
        loops.append(
            ControlLoop(
                full_cfg.runtime,
                model=model,
                tools=ToolRegistry(),
                memory=memory,
                acceptance=acceptance,
            )
        )
    intent = Intent(
        summary=args.intent or "noop",
        acceptance_tasks=full_cfg.runtime.acceptance_tasks,
    )
    return loops, intent, full_cfg


@register_task("topology-pipeline")
def task_topology_pipeline(args: argparse.Namespace, context: HarnessContext) -> int:
    from runtime import PipelineTopology, runtime_config_from_harness

    stage_count = len(runtime_config_from_harness().topology.pipeline_default_stages)
    loops, intent, full_cfg = _build_topology_loops(args, context, count=stage_count)
    pipeline = PipelineTopology(loops, cfg=full_cfg.topology)
    results = pipeline.run(intent)
    accepted = all(r.accepted for r in results)
    LOGGER.info(
        "topology-pipeline accepted=%s stages=%d", accepted, len(results),
    )
    return 0 if accepted else 1


@register_task("topology-fanout")
def task_topology_fanout(args: argparse.Namespace, context: HarnessContext) -> int:
    from runtime import (
        FanOutFanInTopology,
        MapExecutor,
        runtime_config_from_harness,
    )

    workers = runtime_config_from_harness().topology.fanout_default_workers
    loops, intent, full_cfg = _build_topology_loops(args, context, count=workers)
    topology = FanOutFanInTopology(
        loops,
        cfg=full_cfg.topology,
        executor_factory=lambda n: MapExecutor(n),
    )
    results = topology.run(intent)
    merged = results[-1]
    LOGGER.info("topology-fanout accepted=%s", merged.accepted)
    return 0 if merged.accepted else 1


@register_task("topology-producer-reviewer")
def task_topology_producer_reviewer(
    args: argparse.Namespace, context: HarnessContext
) -> int:
    from runtime import ProducerReviewerTopology

    loops, intent, full_cfg = _build_topology_loops(args, context, count=2)
    topology = ProducerReviewerTopology(
        producer=loops[0], reviewer=loops[1], cfg=full_cfg.topology,
    )
    results = topology.run(intent)
    accepted = bool(results) and all(r.accepted for r in results[-2:])
    LOGGER.info(
        "topology-producer-reviewer accepted=%s rounds=%d",
        accepted, len(results) // 2,
    )
    return 0 if accepted else 1


@register_task("topology-expert-pool")
def task_topology_expert_pool(
    args: argparse.Namespace, context: HarnessContext
) -> int:
    from runtime import ExpertPoolTopology, runtime_config_from_harness

    quorum = runtime_config_from_harness().topology.expert_pool_min_quorum
    loops, intent, full_cfg = _build_topology_loops(args, context, count=quorum)
    topology = ExpertPoolTopology(loops, cfg=full_cfg.topology)
    results = topology.run(intent)
    merged = results[-1]
    LOGGER.info("topology-expert-pool accepted=%s", merged.accepted)
    return 0 if merged.accepted else 1


@register_task("mock-publish-detection")
def task_mock_publish_detection(args: argparse.Namespace, context: HarnessContext) -> int:
    cfg = load_wildlife_config(context.config.wildlife_config)
    mqtt_cfg = cfg["mqtt"]
    topic = topic_from_pattern(mqtt_cfg["topics"]["detections"], args.node_id)
    auth = None
    if mqtt_cfg.get("username") or mqtt_cfg.get("password"):
        auth = {
            "username": mqtt_cfg.get("username", ""),
            "password": mqtt_cfg.get("password", ""),
        }

    for index in range(args.count):
        payload = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "frame_id": f"{args.frame_prefix}_{index:03d}",
            "model": args.model,
            "fps": args.fps,
            "detections": [
                {
                    "class_id": args.class_id,
                    "class_name": args.class_name,
                    "confidence": args.confidence,
                    "bbox": [args.bbox_x, args.bbox_y, args.bbox_w, args.bbox_h],
                }
            ],
        }
        LOGGER.info("Publishing detection to %s: %s", topic, json.dumps(payload))
        if args.dry_run:
            continue
        mqtt_publish.single(
            topic,
            json.dumps(payload),
            hostname=mqtt_cfg["host"],
            port=int(mqtt_cfg["port"]),
            qos=1,
            auth=auth,
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Wildlife Watcher agent harness")
    parser.add_argument("task", choices=sorted(TASKS))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--node-id",
        default="sim-01",
        help="MQTT node identifier for mock publishing",
    )
    parser.add_argument(
        "--frame-prefix",
        default="sim",
        help="Frame ID prefix for mock detection payloads",
    )
    parser.add_argument(
        "--class-name",
        default="bird",
        help="Class name for mock detection payloads",
    )
    parser.add_argument(
        "--class-id",
        type=int,
        default=14,
        help="Class ID for mock detection payloads",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.92,
        help="Confidence score for mock detection payloads",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of mock detection messages to publish",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=10.0,
        help="FPS value to include in mock payloads",
    )
    parser.add_argument(
        "--model",
        default="simulated-yolo",
        help="Model name to include in mock payloads",
    )
    parser.add_argument("--bbox-x", type=int, default=10, help="Bounding box x coordinate")
    parser.add_argument("--bbox-y", type=int, default=20, help="Bounding box y coordinate")
    parser.add_argument("--bbox-w", type=int, default=120, help="Bounding box width")
    parser.add_argument("--bbox-h", type=int, default=90, help="Bounding box height")
    parser.add_argument(
        "--intent",
        default=None,
        help="Natural-language intent passed to runtime/ralph/topology tasks",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Override [runtime].max_iterations / [ralph].max_iterations",
    )
    parser.add_argument(
        "--shard-id",
        default=None,
        help="Slice identifier for spec-shard task",
    )
    parser.add_argument(
        "--shard-spec",
        default=None,
        help="Override default SPEC.md content for spec-shard task",
    )
    parser.add_argument(
        "--shard-task",
        default=None,
        help="Override default task.md content for spec-shard task",
    )
    parser.add_argument(
        "--shard-learnings",
        default=None,
        help="Override default learnings.md content for spec-shard task",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(args.verbose)
    context = HarnessContext(config=load_config())
    return TASKS[args.task](args, context)


if __name__ == "__main__":
    raise SystemExit(main())
