from __future__ import annotations

import numpy as np
import pytest
from wildlife_ml.data.augment import center_crop, random_horizontal_flip


def test_random_horizontal_flip_rejects_2d_image() -> None:
    with pytest.raises(ValueError, match="HxWx3"):
        random_horizontal_flip(np.zeros((4, 4), dtype=np.uint8), seed=0)


def test_random_horizontal_flip_rejects_non_uint8() -> None:
    with pytest.raises(ValueError, match="uint8"):
        random_horizontal_flip(np.zeros((4, 4, 3), dtype=np.float32), seed=0)


def test_random_horizontal_flip_zero_probability_is_identity() -> None:
    img = np.arange(48, dtype=np.uint8).reshape(4, 4, 3)
    out = random_horizontal_flip(img, seed=0, probability=0.0)
    np.testing.assert_array_equal(out, img)


def test_random_horizontal_flip_probability_one_always_flips() -> None:
    img = np.arange(48, dtype=np.uint8).reshape(4, 4, 3)
    out = random_horizontal_flip(img, seed=0, probability=1.0)
    np.testing.assert_array_equal(out, np.flip(img, axis=1))


def test_center_crop_rejects_oversize_request() -> None:
    img = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="must fit"):
        center_crop(img, crop_height=10, crop_width=2)
