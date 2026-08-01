from pathlib import Path

from PIL import Image

from app.image_quality import upscale_image


def test_upscale_creates_large_high_quality_scene(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    destination = tmp_path / "result.jpg"
    Image.new("RGB", (240, 160), (25, 45, 90)).save(source, quality=70)

    upscale_image(source, destination)

    with Image.open(destination) as image:
        assert image.size == (1280, 960)
        assert image.format == "JPEG"
    assert destination.stat().st_size > 10_000
