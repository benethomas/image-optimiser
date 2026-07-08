"""Application factory and shared extensions."""
from flask import Flask, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .config import Config

# Rate limiting keyed by client IP. Configured (storage, headers) from app
# config in create_app; the per-route budget lives on the /optimize view.
limiter = Limiter(key_func=get_remote_address)


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(config_class)
    config_class.init_app(app)

    limiter.init_app(app)

    from .routes import bp
    app.register_blueprint(bp)

    _register_error_handlers(app)

    from .cleanup import start_cleanup
    start_cleanup(app)

    return app


def _register_error_handlers(app):
    """Return JSON for the errors the upload flow can hit, so the frontend can
    always parse ``response.error``."""

    @app.errorhandler(413)
    def too_large(_):
        return jsonify(error="File is too large. The maximum size is 25 MB."), 413

    @app.errorhandler(429)
    def rate_limited(_):
        return (
            jsonify(error="Too many requests. Please wait a minute and try again."),
            429,
        )
