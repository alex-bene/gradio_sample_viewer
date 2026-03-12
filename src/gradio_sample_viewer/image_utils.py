"""Image loading and resizing helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from pathlib import Path


def resize_image_max_side(image: Image.Image, max_size: int | None = None) -> Image.Image:
    """Resize image so the largest side is `max_size` while preserving aspect ratio."""
    if max_size is None or max_size <= 0:
        return image.copy()

    width, height = image.size
    largest_side = max(width, height)
    if largest_side <= max_size:
        return image.copy()

    scale = max_size / largest_side
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(new_size, resample=Image.Resampling.LANCZOS)


def load_resized_image(image_path: str | Path, max_size: int) -> Image.Image:
    """Load image from disk and optionally downsample it to `max_size`."""
    with Image.open(image_path) as image:
        loaded_image = image.copy()
    return resize_image_max_side(loaded_image, max_size)
