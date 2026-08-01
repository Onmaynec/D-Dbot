from __future__ import annotations

from pathlib import Path


def upscale_image(source: Path, destination: Path, target_size: tuple[int, int] = (1280, 960)) -> None:
    """Создаёт крупную JPEG-сцену без чёрных полос и грубого масштабирования."""
    from PIL import Image, ImageFilter, ImageOps

    with Image.open(source) as opened:
        image = opened.convert("RGB")
        background = ImageOps.fit(
            image,
            target_size,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        ).filter(ImageFilter.GaussianBlur(radius=24))
        foreground = ImageOps.contain(image, target_size, method=Image.Resampling.LANCZOS)
        foreground = foreground.filter(ImageFilter.UnsharpMask(radius=1.4, percent=105, threshold=2))
        offset = ((target_size[0] - foreground.width) // 2, (target_size[1] - foreground.height) // 2)
        background.paste(foreground, offset)
        destination.parent.mkdir(parents=True, exist_ok=True)
        background.save(
            destination,
            format="JPEG",
            quality=94,
            optimize=True,
            progressive=True,
            subsampling=0,
        )
