from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrainConfig:
    dataset_yaml: Path
    output_dir: Path
    model_name: str = "yolov8n.pt"
    epochs: int = 50
    image_size: int = 320
    batch_size: int = 16
    device: str = "cpu"


def build_training_command(config: TrainConfig) -> list[str]:
    return [
        "yolo",
        "detect",
        "train",
        f"data={config.dataset_yaml}",
        f"project={config.output_dir}",
        f"model={config.model_name}",
        f"epochs={config.epochs}",
        f"imgsz={config.image_size}",
        f"batch={config.batch_size}",
        f"device={config.device}",
    ]


def run_training(config: TrainConfig, *, dry_run: bool = False) -> int:
    command = build_training_command(config)
    if dry_run:
        print(" ".join(str(part) for part in command))
        return 0
    completed = subprocess.run(command, check=False)
    return completed.returncode


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build or run the YOLO training command")
    parser.add_argument("--dataset-yaml", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-name", default="yolov8n.pt")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--image-size", type=int, default=320)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    config = TrainConfig(
        dataset_yaml=args.dataset_yaml,
        output_dir=args.output_dir,
        model_name=args.model_name,
        epochs=args.epochs,
        image_size=args.image_size,
        batch_size=args.batch_size,
        device=args.device,
    )
    return run_training(config, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())