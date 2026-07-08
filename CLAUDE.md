# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
python -m venv venv && source venv/bin/activate   # first-time setup
pip install -r requirements.txt

python run.py                                      # dev server -> http://127.0.0.1:5000
gunicorn "app:create_app()"                        # production WSGI entrypoint
```

There is no test suite or linter configured yet.

## Architecture

Flask app using the **application-factory** pattern. `create_app()` in `app/__init__.py`
wires everything together; `run.py` / gunicorn call it. The single user flow is: drag an
image onto the page → `POST /optimize` → server validates, optimizes, and writes a temp
file → JSON stats returned → JS swaps the "after" pane image and download link.

Request path across modules:

- `app/routes.py` — the `main` blueprint. `/optimize` reads the upload fully into memory
  (bounded by `MAX_CONTENT_LENGTH`), then delegates to validators and the optimizer.
  Optimized files are written to `UPLOAD_FOLDER` under a random `<uuid>.<ext>` name and
  served back via `/files/<name>` (regex-guarded, `?download=1` forces attachment).
- `app/validators.py` — **content-based** validation. The allow-list (`JPEG/PNG/WEBP`) is
  checked against the format Pillow *detects*, not the extension, so renamed GIF/SVG and
  spoofed extensions are rejected. `ValidationError` messages are safe to show users.
- `app/optimizer.py` — Pillow save logic per format (JPEG progressive + quality 85, PNG
  optimize, WebP method 6). EXIF is applied then stripped. **OpenCV (`cv2`) is intentionally
  a dependency but off the hot path** — `opencv_available()` exists for future features
  (resize/denoise); don't add it to the core optimize path without reason.
- `app/cleanup.py` — a daemon thread sweeps `UPLOAD_FOLDER`, deleting files older than
  `FILE_TTL_SECONDS`. Guarded against double-start under the debug reloader.
- `app/config.py` — all limits are env-overridable: `MAX_CONTENT_LENGTH` (25 MB),
  `FILE_TTL_SECONDS`, `UPLOAD_FOLDER`, rate-limit storage.

## Cross-cutting constraints

- **Rate limiting**: Flask-Limiter, keyed by client IP. The 30/min budget lives as
  `@limiter.limit("30 per minute")` on the `/optimize` view in `app/routes.py`. Default
  storage is in-memory (`memory://`) — fine for one process; set `RATELIMIT_STORAGE_URI`
  (e.g. Redis) before running multiple workers or the counts won't be shared.
- **Error contract**: the frontend always reads `response.error` from JSON. Any new
  failure mode (including 413/429, handled in `_register_error_handlers`) must return JSON
  with an `error` key, never an HTML error page.
- **Never leak internals**: optimizer/Pillow exceptions are caught in the route and
  returned as a generic message; details go to `current_app.logger`.
