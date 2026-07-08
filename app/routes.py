"""HTTP routes.

- GET  /            -> the drag-and-drop UI
- POST /optimize    -> validate + optimize an upload, return the optimised
                       image bytes with stats in the ``X-Optimize-Meta`` header.

The optimised image is returned inline in the response body. Nothing is written
to disk, so uploaded images are never retained (see optimizer.py).
"""
import json

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    render_template,
    request,
)

from . import limiter
from .optimizer import (
    BLUR_DEFAULT,
    BLUR_MAX,
    BLUR_MIN,
    BRIGHTNESS_DEFAULT,
    BRIGHTNESS_MAX,
    BRIGHTNESS_MIN,
    CONTRAST_DEFAULT,
    CONTRAST_MAX,
    CONTRAST_MIN,
    DEFAULT_PRESET,
    EXT_BY_FORMAT,
    MIME_BY_FORMAT,
    OUTPUT_FORMATS,
    PRESETS,
    QUALITY_DEFAULT,
    QUALITY_MAX,
    QUALITY_MIN,
    RESIZE_DEFAULT,
    RESIZE_MAX,
    RESIZE_MIN,
    SHARPEN_DEFAULT,
    SHARPEN_MAX,
    SHARPEN_MIN,
    clamp,
    effective_quality,
    optimize_image,
    resolve_output_format,
)
from .validators import validate_image, ValidationError

bp = Blueprint("main", __name__)

_TRUE = {"1", "true", "yes", "on"}


def _int_param(name, default, low, high):
    """Parse an int form field, clamping to [low, high]; default if missing/bad."""
    raw = request.form.get(name)
    if raw is None or raw == "":
        return default
    try:
        return clamp(int(float(raw)), low, high)
    except (TypeError, ValueError):
        return default


def _bool_param(name, default):
    raw = request.form.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE


def _preset_param():
    raw = (request.form.get("preset") or "").strip().lower()
    return raw if raw in PRESETS else DEFAULT_PRESET


@bp.route("/")
def index():
    presets_json = json.dumps(
        {
            name: {"min": cfg["quality_range"][0], "max": cfg["quality_range"][1]}
            for name, cfg in PRESETS.items()
        }
    )
    return render_template(
        "index.html",
        quality_min=QUALITY_MIN,
        quality_max=QUALITY_MAX,
        quality_default=QUALITY_DEFAULT,
        resize_min=RESIZE_MIN,
        resize_max=RESIZE_MAX,
        resize_default=RESIZE_DEFAULT,
        brightness_min=BRIGHTNESS_MIN,
        brightness_max=BRIGHTNESS_MAX,
        brightness_default=BRIGHTNESS_DEFAULT,
        contrast_min=CONTRAST_MIN,
        contrast_max=CONTRAST_MAX,
        contrast_default=CONTRAST_DEFAULT,
        sharpen_min=SHARPEN_MIN,
        sharpen_max=SHARPEN_MAX,
        sharpen_default=SHARPEN_DEFAULT,
        blur_min=BLUR_MIN,
        blur_max=BLUR_MAX,
        blur_default=BLUR_DEFAULT,
        output_formats=list(OUTPUT_FORMATS),
        presets=list(PRESETS.keys()),
        default_preset=DEFAULT_PRESET,
        presets_json=presets_json,
    )


@bp.route("/optimize", methods=["POST"])
@limiter.limit("30 per minute")
def optimize():
    if "image" not in request.files:
        return jsonify(error="No file was provided."), 400

    file = request.files["image"]
    if not file.filename:
        return jsonify(error="No file was selected."), 400

    raw = file.read()  # bounded by MAX_CONTENT_LENGTH (413 handled globally)

    try:
        fmt = validate_image(raw, file.filename)
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400

    preset = _preset_param()
    output_fmt = resolve_output_format(request.form.get("format"), fmt)
    quality_requested = _int_param("quality", QUALITY_DEFAULT, QUALITY_MIN, QUALITY_MAX)
    quality = effective_quality(quality_requested, preset)
    resize_percent = _int_param("resize", RESIZE_DEFAULT, RESIZE_MIN, RESIZE_MAX)
    brightness = _int_param("brightness", BRIGHTNESS_DEFAULT, BRIGHTNESS_MIN, BRIGHTNESS_MAX)
    contrast = _int_param("contrast", CONTRAST_DEFAULT, CONTRAST_MIN, CONTRAST_MAX)
    sharpen = _int_param("sharpen", SHARPEN_DEFAULT, SHARPEN_MIN, SHARPEN_MAX)
    blur = _int_param("blur", BLUR_DEFAULT, BLUR_MIN, BLUR_MAX)
    strip_metadata = _bool_param("strip", True)
    auto_orient = _bool_param("orient", True)

    try:
        data, meta = optimize_image(
            raw,
            fmt,
            output_fmt=output_fmt,
            quality=quality,
            resize_percent=resize_percent,
            strip_metadata=strip_metadata,
            auto_orient=auto_orient,
            preset=preset,
            brightness=brightness,
            contrast=contrast,
            sharpen=sharpen,
            blur=blur,
        )
    except Exception:  # noqa: BLE001 - never leak Pillow internals to the client
        current_app.logger.exception("Optimization failed for %s", file.filename)
        return jsonify(error="Could not process this image."), 500

    original_size = len(raw)
    optimized_size = len(data)
    savings = round((1 - optimized_size / original_size) * 100, 1) if original_size else 0

    is_png = output_fmt == "PNG"
    meta_header = {
        "format": output_fmt,
        "source_format": fmt,
        "converted": output_fmt != fmt,
        "download_name": f"optimized.{EXT_BY_FORMAT[output_fmt]}",
        "original_size": original_size,
        "optimized_size": optimized_size,
        "savings": savings,
        **meta,
        "applied": {
            "preset": preset,
            "output_format": output_fmt,
            "quality": None if is_png else quality,
            "quality_requested": None if is_png else quality_requested,
            "resize_percent": resize_percent,
            "brightness": brightness,
            "contrast": contrast,
            "sharpen": sharpen,
            "blur": blur,
            "strip_metadata": strip_metadata,
            "auto_orient": auto_orient,
            "lossless": is_png,
        },
    }

    resp = Response(data, mimetype=MIME_BY_FORMAT[output_fmt])
    resp.headers["X-Optimize-Meta"] = json.dumps(meta_header)
    resp.headers["Cache-Control"] = "no-store"
    return resp
