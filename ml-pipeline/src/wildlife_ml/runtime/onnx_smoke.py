from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from wildlife_ml.export.onnx import prepare_image_batch
from wildlife_ml.types import Float32Tensor, UInt8Image


def dry_run_smoke_summary(
    model_path: Path,
    image_size: tuple[int, int] = (320, 320),
) -> dict[str, object]:
    height, width = image_size
    synthetic: UInt8Image = np.zeros((height, width, 3), dtype=np.uint8)
    batch: Float32Tensor = prepare_image_batch(synthetic)
    return {
        "model_path": str(model_path),
        "input_shape": tuple(int(value) for value in batch.shape),
        "dtype": str(batch.dtype),
        "max_value": float(batch.max()),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a dry-run ONNX smoke summary")
    parser.add_argument("--model-path", type=Path, default=Path("models/model.onnx"))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = dry_run_smoke_summary(args.model_path)
    for key, value in summary.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
