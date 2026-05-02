from __future__ import annotations

from typing import Any, cast

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
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


@given(
    h=st.integers(min_value=4, max_value=64),
    w=st.integers(min_value=4, max_value=64),
)
@settings(max_examples=25)
def test_prepare_image_batch_output_shape_and_range(h: int, w: int) -> None:
    """For any HxW uint8 image, the batch has shape (1,3,out_h,out_w) and
    values in [0.0, 1.0]."""
    image = np.zeros((h, w, 3), dtype=np.uint8)
    image[0, 0, 0] = 255  # ensure the full value range is exercised
    out_h, out_w = 8, 8
    batch = prepare_image_batch(image, OnnxExportConfig(image_size=(out_h, out_w)))
    assert batch.shape == (1, 3, out_h, out_w)
    assert batch.dtype == np.float32
    assert float(batch.min()) >= 0.0
    assert float(batch.max()) <= 1.0
