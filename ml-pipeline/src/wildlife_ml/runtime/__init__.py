from __future__ import annotations

from pathlib import Path


def dry_run_smoke_summary(model_path: Path, image_size: tuple[int, int] = (320, 320)) -> dict[str, object]:
	from wildlife_ml.runtime.onnx_smoke import dry_run_smoke_summary as _dry_run_smoke_summary

	return _dry_run_smoke_summary(model_path, image_size)


__all__ = ["dry_run_smoke_summary"]