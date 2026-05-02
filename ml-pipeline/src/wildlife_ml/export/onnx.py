from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from wildlife_ml.types import Float32Tensor, UInt8Image


@dataclass(frozen=True)
class OnnxExportConfig:
    image_size: tuple[int, int] = (320, 320)
    input_name: str = "images"
    output_name: str = "predictions"
    opset: int = 13


def _resize_nearest(image: UInt8Image, image_size: tuple[int, int]) -> UInt8Image:
    target_height, target_width = image_size
    src_height, src_width, _ = image.shape
    y_idx = np.linspace(0, src_height - 1, target_height).astype(np.int64)
    x_idx = np.linspace(0, src_width - 1, target_width).astype(np.int64)
    resized = image[y_idx][:, x_idx]
    return np.ascontiguousarray(resized)


def prepare_image_batch(image: UInt8Image, config: OnnxExportConfig | None = None) -> Float32Tensor:
    resolved = config or OnnxExportConfig()
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f"Expected HxWx3 image, got {image.shape!r}")
    if image.dtype != np.uint8:
        raise ValueError(f"Expected uint8 image, got {image.dtype!r}")

    resized = _resize_nearest(image, resolved.image_size)
    chw = np.transpose(resized.astype(np.float32) / 255.0, (2, 0, 1))
    batch = np.expand_dims(chw, axis=0)
    return np.ascontiguousarray(batch, dtype=np.float32)


def build_export_command(
    weights_path: Path,
    output_dir: Path,
    config: OnnxExportConfig | None = None,
) -> list[str]:
    resolved = config or OnnxExportConfig()
    image_height, image_width = resolved.image_size
    return [
        "yolo",
        "export",
        f"model={weights_path}",
        "format=onnx",
        f"imgsz={image_height},{image_width}",
        f"opset={resolved.opset}",
        f"project={output_dir}",
    ]


def run_export(weights_path: Path, output_dir: Path, *, dry_run: bool = False) -> int:
    command = build_export_command(weights_path, output_dir)
    if dry_run:
        print(" ".join(str(part) for part in command))
        return 0
    completed = subprocess.run(command, check=False)
    return completed.returncode


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build or run the ONNX export command")
    parser.add_argument("--weights-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    return run_export(args.weights_path, args.output_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())