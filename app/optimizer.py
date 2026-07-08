"""Image optimization using Pillow.

The pipeline is fully in-memory: bytes in, bytes out. Nothing is written to
disk, so uploaded images are never retained beyond the lifetime of the request.

OpenCV (cv2) is imported lazily and kept available for future features such as
smart resizing, denoising, or perceptual tuning. It is not on the current
optimization path, so the app still runs if cv2 fails to import.
"""
import io

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

# Format -> output file extension / MIME type.
EXT_BY_FORMAT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
MIME_BY_FORMAT = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}

# Output formats the user may convert to. Empty/"original" keeps the input
# format. Kept in sync with the validator's allow-list.
OUTPUT_FORMATS = ("JPEG", "PNG", "WEBP")

# Lossy quality bounds (JPEG/WebP). PNG is lossless and ignores quality.
QUALITY_MIN, QUALITY_MAX, QUALITY_DEFAULT = 1, 95, 85

# Resize as a percentage of the original, aspect ratio preserved.
RESIZE_MIN, RESIZE_MAX, RESIZE_DEFAULT = 10, 200, 100

# Enhancement adjustments. Brightness/contrast are percentages where 100 means
# "no change" (enhance factor 1.0). Sharpen/blur are amounts where 0 means off.
BRIGHTNESS_MIN, BRIGHTNESS_MAX, BRIGHTNESS_DEFAULT = 0, 200, 100
CONTRAST_MIN, CONTRAST_MAX, CONTRAST_DEFAULT = 0, 200, 100
SHARPEN_MIN, SHARPEN_MAX, SHARPEN_DEFAULT = 0, 100, 0
BLUR_MIN, BLUR_MAX, BLUR_DEFAULT = 0, 100, 0

# Blur slider (0-100) maps linearly onto a Gaussian radius of 0-BLUR_MAX_RADIUS
# pixels. Sharpen slider (0-100) scales UnsharpMask's percent up to
# SHARPEN_MAX_PERCENT. These keep the raw filter params off the wire.
BLUR_MAX_RADIUS = 8.0
SHARPEN_MAX_PERCENT = 300

# Speed <-> quality presets. Each maps to encoder effort/params and a soft
# quality range that clamps the user's slider. The clamp is intentional and
# documented: "speed" caps quality for fast encodes, "max_quality" raises a
# floor. The effective (post-clamp) quality is surfaced back to the UI.
PRESETS = {
    "speed": {
        "quality_range": (QUALITY_MIN, 85),
        "webp_method": 1,        # low effort, fast
        "jpeg_subsampling": 2,   # 4:2:0 (smallest, some chroma loss)
        "jpeg_optimize": False,
        "jpeg_progressive": False,
        "png_compress_level": 3,
        "png_optimize": False,
    },
    "balanced": {
        "quality_range": (QUALITY_MIN, QUALITY_MAX),
        "webp_method": 4,
        "jpeg_subsampling": 2,   # 4:2:0
        "jpeg_optimize": True,
        "jpeg_progressive": True,
        "png_compress_level": 6,
        "png_optimize": False,
    },
    "max_quality": {
        "quality_range": (80, QUALITY_MAX),
        "webp_method": 6,        # highest effort, slowest
        "jpeg_subsampling": 0,   # 4:4:4, no chroma subsampling
        "jpeg_optimize": True,
        "jpeg_progressive": True,
        "png_compress_level": 9,
        "png_optimize": True,
    },
}
DEFAULT_PRESET = "balanced"


def opencv_available() -> bool:
    """Whether cv2 can be imported. Handy for a future /features endpoint."""
    try:
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def effective_quality(requested: int, preset: str) -> int:
    """Apply the preset's soft quality clamp to a requested value."""
    low, high = PRESETS[preset]["quality_range"]
    return clamp(requested, low, high)


def resolve_output_format(requested: str, source_fmt: str) -> str:
    """Return the format to encode to: the requested one, or the source if unset.

    ``requested`` may be an OUTPUT_FORMATS value (case-insensitive) or empty /
    ``"original"`` to keep ``source_fmt``. Unknown values fall back to the source.
    """
    normalized = (requested or "").strip().upper()
    if normalized in OUTPUT_FORMATS:
        return normalized
    return source_fmt


def _apply_adjustments(img, brightness, contrast, sharpen, blur):
    """Apply brightness/contrast/blur/sharpen. No-ops pass through untouched.

    ImageEnhance and the blur/sharpen filters need a real RGB(A) raster, so a
    palette ("P") image is promoted first. Order is deliberate: tonal changes,
    then blur, then sharpen (so sharpening acts on the final pixels).
    """
    if brightness == BRIGHTNESS_DEFAULT and contrast == CONTRAST_DEFAULT \
            and sharpen == SHARPEN_MIN and blur == BLUR_MIN:
        return img

    if img.mode == "P":
        img = img.convert("RGBA" if "transparency" in img.info else "RGB")

    if brightness != BRIGHTNESS_DEFAULT:
        img = ImageEnhance.Brightness(img).enhance(brightness / 100)
    if contrast != CONTRAST_DEFAULT:
        img = ImageEnhance.Contrast(img).enhance(contrast / 100)
    if blur > BLUR_MIN:
        radius = blur / BLUR_MAX * BLUR_MAX_RADIUS
        img = img.filter(ImageFilter.GaussianBlur(radius=radius))
    if sharpen > SHARPEN_MIN:
        percent = round(sharpen / SHARPEN_MAX * SHARPEN_MAX_PERCENT)
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=percent, threshold=3))

    return img


def optimize_image(
    raw: bytes,
    fmt: str,
    *,
    output_fmt: str,
    quality: int,
    resize_percent: int,
    strip_metadata: bool,
    auto_orient: bool,
    preset: str,
    brightness: int = BRIGHTNESS_DEFAULT,
    contrast: int = CONTRAST_DEFAULT,
    sharpen: int = SHARPEN_MIN,
    blur: int = BLUR_MIN,
):
    """Optimize ``raw`` (bytes of format ``fmt``) and return ``(bytes, meta)``.

    ``output_fmt`` is the format to encode to (one of OUTPUT_FORMATS), which may
    differ from the input ``fmt`` for format conversion. ``quality`` is expected
    to already be the effective (post-clamp) value. ``meta`` reports original and
    output dimensions.
    """
    cfg = PRESETS[preset]

    with Image.open(io.BytesIO(raw)) as img:
        # Bake in EXIF orientation first; exif_transpose also drops the
        # orientation tag from the returned image's metadata, so preserved
        # EXIF (below) won't cause viewers to double-rotate.
        if auto_orient:
            img = ImageOps.exif_transpose(img)

        original_width, original_height = img.size

        # Metadata to carry over only when the user opts out of stripping.
        # Captured after exif_transpose so orientation is already normalised.
        exif = None if strip_metadata else img.info.get("exif")
        icc = None if strip_metadata else img.info.get("icc_profile")

        if resize_percent != 100:
            new_w = max(1, round(original_width * resize_percent / 100))
            new_h = max(1, round(original_height * resize_percent / 100))
            img = img.resize((new_w, new_h), Image.LANCZOS)

        img = _apply_adjustments(img, brightness, contrast, sharpen, blur)

        output_width, output_height = img.size

        buf = io.BytesIO()
        if output_fmt == "JPEG":
            # JPEG has no alpha; flatten transparency onto white.
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            kwargs = dict(
                format="JPEG",
                quality=quality,
                optimize=cfg["jpeg_optimize"],
                progressive=cfg["jpeg_progressive"],
                subsampling=cfg["jpeg_subsampling"],
            )
        elif output_fmt == "WEBP":
            kwargs = dict(format="WEBP", quality=quality, method=cfg["webp_method"])
        elif output_fmt == "PNG":
            kwargs = dict(
                format="PNG",
                optimize=cfg["png_optimize"],
                compress_level=cfg["png_compress_level"],
            )
        else:  # pragma: no cover - routes guarantee output_fmt is allowed
            raise ValueError(f"Unsupported format: {output_fmt}")

        if exif:
            kwargs["exif"] = exif
        if icc:
            kwargs["icc_profile"] = icc

        img.save(buf, **kwargs)

    return buf.getvalue(), {
        "original_width": original_width,
        "original_height": original_height,
        "output_width": output_width,
        "output_height": output_height,
    }
