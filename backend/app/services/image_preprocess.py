from io import BytesIO

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


def inspect_image_dimensions(image_bytes: bytes, min_size: int = 32) -> tuple[int, int]:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image = ImageOps.exif_transpose(image)
            width, height = image.size
            if width < min_size or height < min_size:
                raise ValueError(f"图像尺寸过小，最小边需要 >= {min_size}px")
            return int(width), int(height)
    except UnidentifiedImageError as exc:
        raise ValueError("图像无法解码") from exc


def load_rgb_square(image_bytes: bytes, output_size: int = 1024, min_size: int = 32) -> np.ndarray:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB")
            width, height = image.size
            target_size = int(output_size)
            if target_size <= 0:
                raise ValueError("输出尺寸必须大于 0")

            min_required = max(int(min_size), target_size)
            if width < min_required or height < min_required:
                raise ValueError(f"图像尺寸过小，最小边需要 >= {min_required}px")

            left = (width - target_size) // 2
            top = (height - target_size) // 2
            image = image.crop((left, top, left + target_size, top + target_size))
            return np.asarray(image, dtype=np.uint8)
    except UnidentifiedImageError as exc:
        raise ValueError("图像无法解码") from exc
