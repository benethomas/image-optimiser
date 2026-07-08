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
- **Real before / after comparison** — the optimised image is rendered side-by-side with the
  original, with size, dimensions and % saved
- **Quality slider** (1–95, default 85) for JPEG and WebP
- **Resize by percent** (10–200%, aspect ratio preserved)
- **Strip-metadata toggle** (default: strip — removes EXIF/GPS for privacy)
- **Auto-orient** from EXIF (default on), baked into the pixels
- **Speed ↔ quality presets** (`speed`, `balanced`, `max_quality`) that map to encoder
  settings and softly constrain the quality slider — see [Presets](#presets)
- **Live parameter preview** — options are reflected instantly; the image re-encodes when a
  control settles (no heavy client-side image processing)
- **Format-safe**: accepts JPEG, PNG and WebP only — validated by *decoding* the file,
  so renamed GIFs, SVGs and spoofed extensions are rejected
- **No retention** — optimisation is fully in-memory; nothing is ever written to disk
- **Rate limiting** — 30 requests/minute per IP
- **25 MB upload cap** enforced before the file is read
- **OpenCV kept on hand** for future features (smart resize, denoise) without bloating the current path

## Presets

Each preset maps to encoder effort/parameters and a **soft quality range** that clamps the
slider. The effective quality is shown live in the UI and returned with the result.

| Preset | Quality range | JPEG | WebP effort | PNG |
| --- | --- | --- | --- | --- |
| `speed` | 1–85 (caps high values) | 4:2:0, no progressive | `method=1` | `compress_level=3` |
| `balanced` *(default)* | 1–95 (full) | 4:2:0, progressive, optimize | `method=4` | `compress_level=6` |
| `max_quality` | 80–95 (raises a floor) | 4:4:4, progressive, optimize | `method=6` | `compress_level=9`, optimize |

PNG is lossless, so the quality slider is ignored for PNG uploads (the UI disables it).

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
| `HOST` / `PORT` | `127.0.0.1` / `5000` | Dev server bind address (`run.py` only) |
| `RATELIMIT_STORAGE_URI` | `memory://` | Rate-limit backend; use Redis for multiple workers |

The 25 MB upload cap and the 30/min rate limit are set in `app/config.py` and `app/routes.py`.
Optimisation is fully in-memory, so there are no temp-file or retention settings.

## Project structure

```
app/
  __init__.py    # application factory + JSON error handlers
  config.py      # env-overridable settings
  routes.py      # / and /optimize (in-memory, returns image + X-Optimize-Meta)
  validators.py  # content-based format validation
  optimizer.py   # Pillow optimisation logic + presets
templates/       # base + index (drag-drop UI + options)
static/          # css + upload.js
run.py           # dev entrypoint
```

The `/optimize` endpoint returns the optimised image **inline in the response body**, with
size/dimension/applied-settings stats in the `X-Optimize-Meta` JSON header. The browser turns
the bytes into an object URL for the preview and download — nothing is persisted server-side.

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
