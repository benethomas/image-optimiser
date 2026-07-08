# Session Notes

# Session 1 - Complete
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
- `POST /optimize` — form fields: `image`, `preset`, `format`, `quality`, `resize`,
  `brightness`, `contrast`, `sharpen`, `blur`, `strip`, `orient`. On success returns image
  bytes + `X-Optimize-Meta` JSON header; on failure returns `{ "error": ... }` with
  400/413/429/500.

## Possible next steps

- Screenshot / demo GIF in the README (placeholder is already there).
- Repo description + topics on GitHub.
- A small CI workflow (lint / smoke test).
- Optional: use the on-hand OpenCV dependency for smart resize/denoise features.

# Session 2 - Complete

Implementing advanced features.

- Sharpen controls — sliders for sharpening, blur, contrast, brightness.
- Format conversion — ability to convert between formats (JPEG, PNG, WebP).

## What was added

- **Adjustments** (`_apply_adjustments` in `app/optimizer.py`): brightness and contrast via
  `ImageEnhance` (percentages, 100 = unchanged), blur via `ImageFilter.GaussianBlur`, and
  sharpen via `ImageFilter.UnsharpMask` (both 0 = off). Order is tonal → blur → sharpen so
  sharpening acts on the final pixels. Runs after resize, before encoding. A palette (`P`)
  image is promoted to RGB/RGBA first (with `transparency` preserved as RGBA).
- **Format conversion**: `optimize_image` now takes `output_fmt` separate from the detected
  input `fmt`. `resolve_output_format()` maps the `format` field (empty/`"original"` → keep
  source; JPEG/PNG/WEBP → convert) and routes uses it for the encoder branch, MIME type,
  extension, download name, and the `is_png` (lossless) logic. PNG→JPEG reuses the existing
  alpha-flatten-onto-white path.
- **UI**: a "Convert to" segmented control (Original/JPEG/PNG/WebP) and a 2×2 grid of
  adjustment sliders. Quality enable/disable and the summary now key off the *output* format
  (choosing PNG output disables quality even for a JPEG upload). Slider `input` updates the
  summary text; a settled `change` re-encodes, same as before.

## Key decisions

- **Output format is authoritative for lossless/quality/MIME**, not the uploaded file's
  format — so "convert JPEG → PNG" correctly reports lossless and ignores quality.
- **Adjustments and format are clamped/validated server-side** like every other param
  (`_int_param` for the sliders, `resolve_output_format` for the format; unknown/bad values
  fall back to safe defaults rather than erroring).
- **Still Pillow-only, still in-memory.** OpenCV remains an off-hot-path dependency;
  brightness/contrast/blur/sharpen all use `ImageEnhance`/`ImageFilter`.

## Verification done

Flask test client: baseline JPEG optimise; PNG(RGBA)→JPEG conversion (alpha flattened,
decodes, correct MIME/name); JPEG→WebP and JPEG→PNG (PNG reports lossless, quality n/a);
brightness/contrast/sharpen/blur each change the output bytes on a gradient image and decode
cleanly; out-of-range/garbage params (`brightness=9999`, `sharpen=abc`, `format=BMP`) clamp
to defaults with a 200; palette and palette+transparency images pass through adjustments;
renamed-GIF still rejected. Page renders all new controls; `upload.js` passes `node --check`.

Live server (`PORT=5001`): index + CSS/JS assets all 200; a real multipart JPEG→WebP request
with brightness/contrast/sharpen applied returned 200, the correct `image/webp` MIME, an
`X-Optimize-Meta` reflecting the applied params, and bytes that decode as WebP. (Note: tiny
synthetic images can report negative savings — format overhead outweighs the shrink — which
the UI correctly shows as "No reduction".)

# Session 2 Focus (original brief)

- Sharpen Conrols - sliders for sharpening, blur, contrast, brightnewss
- Format Conversion - ability to convert between formats (JPEG, PNG, WebP)