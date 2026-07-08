# Image Optimiser

A single-page Flask web app for optimising images in the browser. Drag and drop
a JPG, PNG or WebP and get a smaller file back, with a live before/after
comparison and download.

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Flask](https://img.shields.io/badge/flask-3.x-black)
![License](https://img.shields.io/badge/license-MIT-green)

<!-- Add a screenshot or demo GIF here once deployed, e.g.:
![Screenshot](docs/screenshot.png)
-->

## Features

- **Drag-and-drop upload** with instant client-side preview and click-to-browse fallback
- **Before / after panes** showing the original alongside the optimised result and the % saved
- **Format-safe**: accepts JPEG, PNG and WebP only — validated by decoding the file,
  so renamed GIFs, SVGs and spoofed extensions are rejected
- **Lossless-ish optimisation** via [Pillow](https://python-pillow.org/): EXIF stripped,
  JPEG saved progressive at quality 85, PNG `optimize`, WebP `method=6`
- **Rate limiting** — 30 requests/minute per IP
- **25 MB upload cap** enforced before the file is read
- **Automatic temp-file cleanup** — a background thread deletes optimised files after 15 minutes
- **OpenCV kept on hand** for future features (smart resize, denoise) without bloating the current path

## Quick start

```bash
git clone https://github.com/benethomas/image-optimiser.git
cd image-optimiser

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

python run.py                   # http://127.0.0.1:5000
```

## Configuration

All settings are optional environment variables (see [`.env.example`](.env.example)):

| Variable | Default | Description |
| --- | --- | --- |
| `SECRET_KEY` | random per start | Flask signing key — **set a fixed value in production** |
| `FLASK_DEBUG` | `0` | Set to `1` to enable debug + auto-reload in dev (`run.py` only) |
| `UPLOAD_FOLDER` | OS temp dir | Where optimised files are written before download |
| `FILE_TTL_SECONDS` | `900` | Lifetime of an optimised file before cleanup |
| `RATELIMIT_STORAGE_URI` | `memory://` | Rate-limit backend; use Redis for multiple workers |

The 25 MB upload cap and the 30/min rate limit are set in `app/config.py` and `app/routes.py`.

## Project structure

```
app/
  __init__.py    # application factory + JSON error handlers
  config.py      # env-overridable settings
  routes.py      # /, /optimize, /files/<name>
  validators.py  # content-based format validation
  optimizer.py   # Pillow optimisation logic
  cleanup.py     # background temp-file sweeper
templates/       # base + index (drag-drop UI)
static/          # css + upload.js
run.py           # dev entrypoint
```

## Running in production

`run.py` is a convenience dev server (debug is off unless `FLASK_DEBUG=1`). For
production, serve with a WSGI server:

```bash
pip install gunicorn
gunicorn "app:create_app()" --bind 0.0.0.0:8000
```

When running more than one worker, set `RATELIMIT_STORAGE_URI` to a shared store
(e.g. Redis) so rate-limit counts are shared across processes.

## Tech stack

Flask · Flask-Limiter · Pillow · OpenCV (headless) · vanilla JS/CSS

## License

MIT — see [LICENSE](LICENSE).
