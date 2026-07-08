"""Development entrypoint: ``python run.py``.

For production use a WSGI server, e.g. ``gunicorn "app:create_app()"``.

Debug mode is OFF by default so it can never be enabled accidentally. Turn it
on for local development with ``FLASK_DEBUG=1 python run.py``.
"""
import os

from app import create_app

app = create_app()


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", 5000)),
        debug=_env_flag("FLASK_DEBUG"),
    )
