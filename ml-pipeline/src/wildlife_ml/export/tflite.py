from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from wildlife_ml.export.onnx import OnnxExportConfig


@dataclass(frozen=True)
class TfliteExportConfig:
    image_size: tuple[int, int] = (320, 320)
    quantization: str = "int8"


def build_tflite_command(
    onnx_model: Path,
    output_dir: Path,
    config: TfliteExportConfig | None = None,
) -> list[str]:
    resolved = config or TfliteExportConfig()
    image_height, image_width = resolved.image_size
    return [
        "python",
        "-m",
        "onnx2tf",
        "-i",
        str(onnx_model),
        "-o",
        str(output_dir),
        "-qt",
        resolved.quantization,
        "-ois",
        "1",
        "3",
        str(image_height),
        str(image_width),
    ]


def run_tflite_export(onnx_model: Path, output_dir: Path, *, dry_run: bool = False) -> int:
    command = build_tflite_command(onnx_model, output_dir)
    if dry_run:
        print(" ".join(command))
        return 0
    completed = subprocess.run(command, check=False)
    return completed.returncode


__all__ = [
    "OnnxExportConfig",
    "TfliteExportConfig",
    "build_tflite_command",
    "run_tflite_export",
]