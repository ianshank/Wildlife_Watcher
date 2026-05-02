from __future__ import annotations

import numpy as np
from hypothesis import given
from hypothesis import strategies as st

from wildlife_ml.data.augment import center_crop, random_horizontal_flip


@given(
    height=st.integers(min_value=8, max_value=32),
    width=st.integers(min_value=8, max_value=32),
    seed=st.integers(min_value=0, max_value=1000),
)
def test_random_horizontal_flip_preserves_shape(height: int, width: int, seed: int) -> None:
    image = np.arange(height * width * 3, dtype=np.uint8).reshape(height, width, 3)
    flipped = random_horizontal_flip(image, seed=seed)
    assert flipped.shape == image.shape
    assert flipped.dtype == image.dtype


@given(
    height=st.integers(min_value=8, max_value=32),
    width=st.integers(min_value=8, max_value=32),
)
def test_center_crop_returns_requested_shape(height: int, width: int) -> None:
    image = np.arange(height * width * 3, dtype=np.uint8).reshape(height, width, 3)
    crop = center_crop(image, crop_height=height - 2, crop_width=width - 2)
    assert crop.shape == (height - 2, width - 2, 3)
    assert crop.dtype == image.dtype