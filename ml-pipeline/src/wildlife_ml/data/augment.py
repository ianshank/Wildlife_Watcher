from __future__ import annotations

import numpy as np

from wildlife_ml.types import UInt8Image


def _validate_image(image: UInt8Image) -> None:
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f"Expected HxWx3 uint8 image, got shape={image.shape!r}")
    if image.dtype != np.uint8:
        raise ValueError(f"Expected uint8 image, got dtype={image.dtype!r}")


def random_horizontal_flip(image: UInt8Image, *, seed: int, probability: float = 0.5) -> UInt8Image:
    _validate_image(image)
    generator = np.random.default_rng(seed)
    if float(generator.random()) > probability:
        return np.ascontiguousarray(image)
    return np.ascontiguousarray(np.flip(image, axis=1))


def center_crop(image: UInt8Image, *, crop_height: int, crop_width: int) -> UInt8Image:
    _validate_image(image)
    image_height, image_width, _ = image.shape
    if crop_height > image_height or crop_width > image_width:
        raise ValueError("Crop dimensions must fit inside the image")
    offset_y = (image_height - crop_height) // 2
    offset_x = (image_width - crop_width) // 2
    cropped = image[offset_y : offset_y + crop_height, offset_x : offset_x + crop_width, :]
    return np.ascontiguousarray(cropped)