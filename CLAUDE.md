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
wires everything together; `run.py` / gunicorn call it. The user flow is: drop an image →
`POST /optimize` with the chosen options → server validates and optimizes **in memory** →
the optimized bytes are returned as the response body with stats in the `X-Optimize-Meta`
header → JS builds an object URL for the "after" preview and download link.

**No retention**: nothing is written to disk. The optimize path is pure bytes-in → bytes-out,
so there is no temp folder, no `/files` route, and no cleanup thread. Keep it that way unless
there's a strong reason — if you must persist, add explicit deletion and document it.

Request path across modules:

- `app/routes.py` — the `main` blueprint. `/optimize` reads the upload fully into memory
  (bounded by `MAX_CONTENT_LENGTH`), parses/clamps the options (`preset`, `quality`,
  `resize`, `strip`, `orient`) via the `_*_param` helpers (never trust client values), then
  calls the optimizer and returns a `Response` of image bytes + a JSON `X-Optimize-Meta`
  header. `index()` passes the preset quality ranges to the template as JSON so the JS can
  mirror the soft-clamp for the live summary.
- `app/validators.py` — **content-based** validation. The allow-list (`JPEG/PNG/WEBP`) is
  checked against the format Pillow *detects*, not the extension, so renamed GIF/SVG and
  spoofed extensions are rejected. `ValidationError` messages are safe to show users.
- `app/optimizer.py` — the single source of truth for optimisation. `PRESETS` maps each
  preset to encoder params **and** a `quality_range` that `effective_quality()` uses to
  softly clamp the slider. `optimize_image(...)` does auto-orient → capture-metadata →
  resize → per-format save, returning `(bytes, meta)`. Bounds/defaults
  (`QUALITY_*`, `RESIZE_*`, `DEFAULT_PRESET`) live here and are imported by routes and the
  template. **OpenCV (`cv2`) is intentionally a dependency but off the hot path** —
  `opencv_available()` exists for future features; don't add it to the optimize path lightly.
- `app/config.py` — env-overridable settings: `MAX_CONTENT_LENGTH` (25 MB), rate-limit
  storage, and the `SECRET_KEY` policy (random ephemeral key + warning when unset).

Frontend (`static/js/upload.js`): slider `input` events update the text summary only (cheap);
a settled `change` on any control re-runs `/optimize` — this keeps the rate limit safe while
still giving a live "after" image. The soft-clamp math is duplicated here (from the injected
`window.OPT_CONFIG.presets`) purely for the summary; the server clamp is authoritative.

## Cross-cutting constraints

- **Rate limiting**: Flask-Limiter, keyed by client IP. The 30/min budget lives as
  `@limiter.limit("30 per minute")` on the `/optimize` view in `app/routes.py`. Default
  storage is in-memory (`memory://`) — fine for one process; set `RATELIMIT_STORAGE_URI`
  (e.g. Redis) before running multiple workers or the counts won't be shared.
- **Error contract**: on failure `/optimize` returns JSON with an `error` key (400/413/429/500);
  on success it returns image bytes + the `X-Optimize-Meta` header. The frontend branches on
  `response.ok`. Any new failure mode (413/429 handled in `_register_error_handlers`) must keep
  the JSON-`error` shape, never an HTML error page.
- **Never leak internals**: optimizer/Pillow exceptions are caught in the route and
  returned as a generic message; details go to `current_app.logger`.
