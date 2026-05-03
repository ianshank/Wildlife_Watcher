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

import paho.mqtt.publish as mqtt_publish
import yaml

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


@register_task("integration-kiosk-mqtt")
def task_integration_kiosk_mqtt(args: argparse.Namespace, context: HarnessContext) -> int:
    return run_named_command("integration-kiosk-mqtt", context, args.dry_run)


@register_task("integration-firmware-format")
def task_integration_firmware_format(args: argparse.Namespace, context: HarnessContext) -> int:
    return run_named_command("integration-firmware-format", context, args.dry_run)


@register_task("integration-schema-parity")
def task_integration_schema_parity(args: argparse.Namespace, context: HarnessContext) -> int:
    return run_named_command("integration-schema-parity", context, args.dry_run)


@register_task("integration-manifest-parity")
def task_integration_manifest_parity(args: argparse.Namespace, context: HarnessContext) -> int:
    return run_named_command("integration-manifest-parity", context, args.dry_run)


@register_task("integration-all")
def task_integration_all(args: argparse.Namespace, context: HarnessContext) -> int:
    for name in (
        "integration-schema-parity",
        "integration-manifest-parity",
        "integration-kiosk-mqtt",
        "integration-firmware-format",
    ):
        exit_code = run_named_command(name, context, args.dry_run)
        if exit_code != 0:
            return exit_code
    return 0


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


@register_task("mock-publish-detection")
def task_mock_publish_detection(args: argparse.Namespace, context: HarnessContext) -> int:
    cfg = load_wildlife_config(context.config.wildlife_config)
    mqtt_cfg = cfg["mqtt"]
    topic = topic_from_pattern(mqtt_cfg["topics"]["detections"], args.node_id)
    auth: Any = None
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
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(args.verbose)
    context = HarnessContext(config=load_config())
    return TASKS[args.task](args, context)


if __name__ == "__main__":
    raise SystemExit(main())
