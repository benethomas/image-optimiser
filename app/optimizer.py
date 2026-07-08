"""Image optimization using Pillow.

OpenCV (cv2) is imported lazily and kept available for future features such as
smart resizing, denoising, or format-specific perceptual tuning. It is not on
the current optimization path, so the app still runs if cv2 fails to import.
"""
import io

from PIL import Image, ImageOps

# Format -> output file extension.
EXT_BY_FORMAT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}

# Lossy quality target for JPEG/WebP. Higher = better quality, larger file.
QUALITY = 85


def opencv_available() -> bool:
    """Whether cv2 can be imported. Handy for a future /features endpoint."""
    try:
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


def optimize_image(raw: bytes, fmt: str, out_path) -> dict:
    """Optimize ``raw`` (bytes of format ``fmt``) and write to ``out_path``.

    Returns metadata about the source image (dimensions). Metadata/EXIF is
    dropped on save, which alone shrinks many phone photos.
    """
    with Image.open(io.BytesIO(raw)) as img:
        # Respect the EXIF orientation flag, then discard it, so the pixels
        # are baked into the correct rotation.
        img = ImageOps.exif_transpose(img)
        width, height = img.size

        if fmt == "JPEG":
            # JPEG has no alpha; flatten transparency onto white.
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            img.save(
                out_path,
                format="JPEG",
                quality=QUALITY,
                optimize=True,
                progressive=True,
            )
        elif fmt == "PNG":
            img.save(out_path, format="PNG", optimize=True)
        elif fmt == "WEBP":
            img.save(out_path, format="WEBP", quality=QUALITY, method=6)
        else:  # pragma: no cover - validators guarantee fmt is allowed
            raise ValueError(f"Unsupported format: {fmt}")

    return {"width": width, "height": height}
