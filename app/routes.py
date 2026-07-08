"""HTTP routes.

- GET  /                 -> the drag-and-drop UI
- POST /optimize         -> validate + optimize an upload, return JSON stats
- GET  /files/<name>     -> serve an optimized file (inline, or ?download=1)
"""
import re
import uuid
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
    send_from_directory,
    abort,
)

from . import limiter
from .optimizer import EXT_BY_FORMAT, optimize_image
from .validators import validate_image, ValidationError

bp = Blueprint("main", __name__)

# Optimized files are always <32 hex chars>.<ext>; used to guard the serve route.
_NAME_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")


@bp.route("/")
def index():
    return render_template("index.html")


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

    name = f"{uuid.uuid4().hex}.{EXT_BY_FORMAT[fmt]}"
    out_path = Path(current_app.config["UPLOAD_FOLDER"]) / name

    try:
        meta = optimize_image(raw, fmt, out_path)
    except Exception:  # noqa: BLE001 - never leak Pillow internals to the client
        current_app.logger.exception("Optimization failed for %s", file.filename)
        return jsonify(error="Could not process this image."), 500

    original_size = len(raw)
    optimized_size = out_path.stat().st_size
    savings = 0
    if original_size:
        savings = round((1 - optimized_size / original_size) * 100, 1)

    return jsonify(
        preview_url=f"/files/{name}",
        download_url=f"/files/{name}?download=1",
        original_size=original_size,
        optimized_size=optimized_size,
        savings=savings,
        width=meta["width"],
        height=meta["height"],
        format=fmt,
    )


@bp.route("/files/<name>")
def files(name):
    if not _NAME_RE.match(name):
        abort(404)
    as_attachment = request.args.get("download") == "1"
    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        name,
        as_attachment=as_attachment,
        download_name=f"optimized.{name.rsplit('.', 1)[-1]}" if as_attachment else None,
    )
