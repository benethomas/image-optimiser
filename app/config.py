"""Application configuration.

Values can be overridden via environment variables so the same code runs in
development and production without edits.
"""
import os
import secrets


class Config:
    # No hardcoded fallback: if SECRET_KEY is unset we generate a random
    # ephemeral key so an insecure, publicly-known secret can never ship.
    # Set SECRET_KEY explicitly in production so it stays stable across
    # restarts and workers (see init_app for the startup warning).
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

    # Reject any upload larger than 25 MB before it is read into memory.
    # Flask aborts the request with 413 when this is exceeded.
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB

    # Rate limiting (Flask-Limiter reads these keys from config).
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True

    @staticmethod
    def init_app(app):
        if not os.environ.get("SECRET_KEY"):
            app.logger.warning(
                "SECRET_KEY not set; using a random ephemeral key. "
                "Set SECRET_KEY in production for a stable secret."
            )
