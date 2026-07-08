"""Upload validation.

Validation is deliberately content-based, not extension-based: the raw bytes
are decoded with Pillow and the *detected* format must be in the allow-list.
This rejects a ``.png`` that is really an SVG, a renamed GIF, etc.
"""
import io

from PIL import Image, UnidentifiedImageError

# Extensions we advertise in the UI / accept attribute.
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

# Pillow format names we accept. Note Pillow reports "JPEG" for .jpg files.
# GIF and SVG are intentionally absent -> they are rejected.
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class ValidationError(Exception):
    """Raised when an upload fails validation. Message is safe to show users."""


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def validate_image(raw: bytes, filename: str) -> str:
    """Return the detected Pillow format, or raise ValidationError.

    Checks, in order: extension allow-list, non-empty, decodable by Pillow,
    and detected format allow-list.
    """
    ext = _extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '.{ext or filename}'. Allowed: JPG, PNG, WebP."
        )

    if not raw:
        raise ValidationError("The uploaded file is empty.")

    try:
        with Image.open(io.BytesIO(raw)) as img:
            fmt = img.format
            img.verify()  # detects truncated / corrupt data
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("File is not a valid image or is corrupted.")

    if fmt not in ALLOWED_FORMATS:
        raise ValidationError(
            f"Unsupported image format '{fmt}'. Allowed: JPG, PNG, WebP."
        )

    return fmt
