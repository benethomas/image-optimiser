# Session Notes

A running record of how this project was built and the decisions behind it.
For usage see [README.md](README.md); for architecture guidance see [CLAUDE.md](CLAUDE.md).

## What this is

A single-page Flask web app that optimises images in the browser: drag-and-drop
a JPG/PNG/WebP, tune options, and get a smaller file back with a live
before/after comparison. Built with Flask + Pillow (OpenCV kept available for
future features).

## Build timeline

1. **Scaffold** — Flask app-factory structure, drag-and-drop UI, content-based
   validation (JPEG/PNG/WebP only), 25 MB cap, 30 req/min rate limit, before/after panes.
2. **Public-ready** — added README, MIT LICENSE, `.env.example`, `.gitignore`;
   initialised git and pushed to GitHub.
3. **Security hardening** — removed the hardcoded `SECRET_KEY` default; debug off by default.
4. **Feature round** — quality slider, resize %, strip-metadata toggle, auto-orient,
   speed/quality presets, live parameter preview, real side-by-side After image,
   and a move to a fully in-memory (zero-retention) pipeline.
5. **UX polish** — shared-scale before/after rendering so resize is visually obvious.

## Key decisions & rationale

- **Content-based validation, not extension-based.** Uploads are decoded with Pillow and
  the *detected* format must be in the allow-list, so a renamed GIF/SVG or spoofed
  extension is rejected. (`app/validators.py`)

- **Fully in-memory, no retention.** The optimise path is bytes-in → bytes-out. The
  optimised image is returned in the response body with stats in the `X-Optimize-Meta`
  header; the browser makes an object URL for preview + download. This is the strongest
  form of "no retention" — nothing ever touches disk — and let us delete the earlier
  temp-file/`/files`-route/background-cleanup machinery entirely.

- **Presets softly clamp quality (documented).** `speed` caps quality at 85, `max_quality`
  raises a floor of 80, `balanced` allows the full 1–95. Presets also map to encoder
  params (JPEG subsampling/progressive, WebP `method`, PNG `compress_level`). The
  effective quality is surfaced back to the UI. Single source of truth in
  `PRESETS`/`effective_quality()` in `app/optimizer.py`; the JS mirrors the clamp only for
  the live summary text (server clamp is authoritative).

- **Live preview without heavy client work.** Slider `input` updates the summary text only;
  a settled `change` (slider release / checkbox / preset) triggers the actual re-encode.
  This keeps requests within the rate limit while still feeling live.

- **Shared-scale comparison.** Before/After are drawn at their true dimensions × one shared
  scale (the larger image fits the pane, the other is proportionally smaller), so resizing
  is visually obvious in both directions without overflowing or distorting.

- **Never trust client params.** All options are parsed and clamped server-side
  (`_int_param`/`_bool_param`/`_preset_param` in `app/routes.py`); bad values fall back to
  safe defaults rather than erroring.

- **Security defaults.** No shipped secret (random ephemeral `SECRET_KEY` + startup warning
  when unset); debug off unless `FLASK_DEBUG=1`; stripping EXIF/GPS is the default; internal
  errors are logged, never leaked to the client.

## Gotchas encountered

- **Port 5000 is taken by macOS AirPlay Receiver** (`ControlCenter`, owned by `launchd`),
  which answers with `403`. It respawns if killed, so the clean fix is either disabling
  "AirPlay Receiver" in System Settings or using another port. We run the dev server on
  **5001** (`PORT=5001 python run.py`); `HOST`/`PORT` are env-configurable.

- **Static file caching.** After editing JS/CSS, hard-refresh the browser (`Cmd+Shift+R`) —
  the dev server serves fresh files from disk, but the browser may cache the old ones.

## Verification done

Exercised via Flask's test client and a live server: index + static assets, JPEG/PNG/WebP
optimisation, quality slider effect, preset soft-clamp (speed→85, max_quality→80), resize
(dimension math), PNG-ignores-quality, metadata strip vs keep, EXIF auto-orient (dimensions
swap), bad-param clamping, rate limit (30 pass / 31st → 429 JSON), 25 MB cap (413 JSON), and
the `no-store` header. No temp files are written.

## Endpoints

- `GET /` — the UI.
- `POST /optimize` — form fields: `image`, `preset`, `quality`, `resize`, `strip`, `orient`.
  On success returns image bytes + `X-Optimize-Meta` JSON header; on failure returns
  `{ "error": ... }` with 400/413/429/500.

## Possible next steps

- Screenshot / demo GIF in the README (placeholder is already there).
- Repo description + topics on GitHub.
- A small CI workflow (lint / smoke test).
- Optional: use the on-hand OpenCV dependency for smart resize/denoise features.
