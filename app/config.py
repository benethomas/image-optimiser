"""Application configuration.

Values can be overridden via environment variables so the same code runs in
development and production without edits.
"""
import os
import tempfile
from pathlib import Path


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")

    # Reject any upload larger than 25 MB before it is read into memory.
    # Flask aborts the request with 413 when this is exceeded.
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB

    # Where optimized files are written before download. Defaults to a
    # dedicated folder under the OS temp dir so nothing lands in the repo.
    UPLOAD_FOLDER = os.environ.get(
        "UPLOAD_FOLDER", str(Path(tempfile.gettempdir()) / "image_optimiser")
    )

    # Temp files older than FILE_TTL_SECONDS are swept every
    # CLEANUP_INTERVAL_SECONDS by the background cleanup thread.
    FILE_TTL_SECONDS = int(os.environ.get("FILE_TTL_SECONDS", 900))  # 15 min
    CLEANUP_INTERVAL_SECONDS = int(os.environ.get("CLEANUP_INTERVAL_SECONDS", 60))

    # Rate limiting (Flask-Limiter reads these keys from config).
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True

    @staticmethod
    def init_app(app):
        Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
