from __future__ import annotations

from typing import Any, cast

import numpy as np
import pytest
from wildlife_ml.export.onnx import OnnxExportConfig, prepare_image_batch


def test_prepare_image_batch_returns_nchw_float32() -> None:
    image = np.arange(12 * 16 * 3, dtype=np.uint8).reshape(12, 16, 3)
    batch = prepare_image_batch(image, OnnxExportConfig(image_size=(8, 8)))
    assert batch.shape == (1, 3, 8, 8)
    assert batch.dtype == np.float32
    assert float(batch.min()) >= 0.0
    assert float(batch.max()) <= 1.0


def test_prepare_image_batch_rejects_wrong_rank() -> None:
    image = np.arange(12 * 16, dtype=np.uint8).reshape(12, 16)
    with pytest.raises(ValueError):
        prepare_image_batch(image)


def test_prepare_image_batch_rejects_wrong_dtype() -> None:
    image = np.zeros((8, 8, 3), dtype=np.float64)
    with pytest.raises(ValueError):
        prepare_image_batch(cast(Any, image))