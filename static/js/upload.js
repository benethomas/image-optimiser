"use strict";

const ACCEPTED_EXTENSIONS = ["jpg", "jpeg", "png", "webp"];
const MAX_BYTES = 25 * 1024 * 1024;
const {
  presets: PRESETS,
  qualityDefault: QUALITY_DEFAULT,
  defaults: ADJUST_DEFAULTS,
} = window.OPT_CONFIG;

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const errorEl = document.getElementById("error");
const summaryEl = document.getElementById("summary");

// Controls
const qualityControl = document.getElementById("quality-control");
const qualityInput = document.getElementById("quality");
const qualityValue = document.getElementById("quality-value");
const qualityHint = document.getElementById("quality-hint");
const resizeInput = document.getElementById("resize");
const resizeValue = document.getElementById("resize-value");
const formatHint = document.getElementById("format-hint");
const brightnessInput = document.getElementById("brightness");
const brightnessValue = document.getElementById("brightness-value");
const contrastInput = document.getElementById("contrast");
const contrastValue = document.getElementById("contrast-value");
const sharpenInput = document.getElementById("sharpen");
const sharpenValue = document.getElementById("sharpen-value");
const blurInput = document.getElementById("blur");
const blurValue = document.getElementById("blur-value");
const stripInput = document.getElementById("strip");
const orientInput = document.getElementById("orient");

// Panes
const beforePane = document.getElementById("before-pane");
const beforeStats = document.getElementById("before-stats");
const beforeSize = document.getElementById("before-size");
const beforeDims = document.getElementById("before-dims");
const afterPane = document.getElementById("after-pane");
const afterPlaceholder = document.getElementById("after-placeholder");
const afterStats = document.getElementById("after-stats");
const afterSize = document.getElementById("after-size");
const afterDims = document.getElementById("after-dims");
const afterSavings = document.getElementById("after-savings");
const downloadLink = document.getElementById("download-link");

// State
let currentFile = null;
let beforeUrl = null;
let afterUrl = null;
let lastMeta = null;

// Max display height of a pane image (keep in sync with .pane__body img in CSS).
const PANE_MAX_H = 320;

/* ---------- helpers ---------- */

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[i]}`;
}

function extensionOf(name) {
  return name.includes(".") ? name.split(".").pop().toLowerCase() : "";
}

// Pillow-style format name for a file's extension.
function formatOf(file) {
  if (!file) return null;
  const ext = extensionOf(file.name);
  if (ext === "jpg" || ext === "jpeg") return "JPEG";
  if (ext === "png") return "PNG";
  if (ext === "webp") return "WEBP";
  return null;
}

function selectedFormat() {
  const checked = document.querySelector('input[name="format"]:checked');
  return checked ? checked.value : "";
}

// The format the output will actually be: the chosen conversion, or the
// uploaded file's own format when "Original" is selected.
function outputFormat() {
  return selectedFormat() || formatOf(currentFile);
}

// PNG output is lossless -> quality is ignored, regardless of input format.
function outputIsPng() {
  return outputFormat() === "PNG";
}

function selectedPreset() {
  const checked = document.querySelector('input[name="preset"]:checked');
  return checked ? checked.value : "balanced";
}

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

// Mirror the server's soft quality clamp so the summary reflects reality.
function effectiveQuality(requested, preset) {
  const range = PRESETS[preset];
  return clamp(requested, range.min, range.max);
}

function revoke(url) {
  if (url) URL.revokeObjectURL(url);
}

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
}
function clearError() {
  errorEl.hidden = true;
  errorEl.textContent = "";
}

/* ---------- live parameter preview (cheap, no image work) ---------- */

function readParams() {
  return {
    preset: selectedPreset(),
    format: selectedFormat(),
    quality: Number(qualityInput.value),
    resize: Number(resizeInput.value),
    brightness: Number(brightnessInput.value),
    contrast: Number(contrastInput.value),
    sharpen: Number(sharpenInput.value),
    blur: Number(blurInput.value),
    strip: stripInput.checked,
    orient: orientInput.checked,
  };
}

const FORMAT_LABELS = { JPEG: "JPEG", PNG: "PNG", WEBP: "WebP" };

function updateSummary() {
  const p = readParams();
  qualityValue.textContent = p.quality;
  resizeValue.textContent = `${p.resize}%`;
  brightnessValue.textContent = `${p.brightness}%`;
  contrastValue.textContent = `${p.contrast}%`;
  sharpenValue.textContent = p.sharpen;
  blurValue.textContent = p.blur;

  const png = outputIsPng();
  const outFmt = outputFormat();
  const parts = [];

  if (currentFile) {
    const src = formatOf(currentFile);
    if (outFmt && outFmt !== src) {
      parts.push(`${FORMAT_LABELS[src] || src} → ${FORMAT_LABELS[outFmt]}`);
    } else {
      parts.push(png ? "PNG (lossless)" : FORMAT_LABELS[outFmt] || "—");
    }
  }
  parts.push(`preset: ${p.preset.replace("_", " ")}`);

  if (png) {
    parts.push("quality: n/a");
  } else {
    const eff = effectiveQuality(p.quality, p.preset);
    parts.push(eff !== p.quality ? `quality: ${eff} (clamped from ${p.quality})` : `quality: ${eff}`);
  }

  parts.push(`size: ${p.resize}%`);

  const adj = [];
  if (p.brightness !== ADJUST_DEFAULTS.brightness) adj.push(`brightness ${p.brightness}%`);
  if (p.contrast !== ADJUST_DEFAULTS.contrast) adj.push(`contrast ${p.contrast}%`);
  if (p.sharpen !== ADJUST_DEFAULTS.sharpen) adj.push(`sharpen ${p.sharpen}`);
  if (p.blur !== ADJUST_DEFAULTS.blur) adj.push(`blur ${p.blur}`);
  parts.push(adj.length ? adj.join(", ") : "no adjustments");

  parts.push(p.strip ? "metadata stripped" : "metadata kept");
  parts.push(p.orient ? "auto-orient on" : "auto-orient off");

  summaryEl.textContent = parts.join(" · ");
}

// PNG output is lossless -> quality has no effect; reflect that in the control.
// Also update the format hint to explain the current conversion choice.
function syncQualityAvailability() {
  const png = outputIsPng();
  qualityInput.disabled = png;
  qualityControl.classList.toggle("is-disabled", png);
  qualityHint.textContent = png
    ? "PNG is lossless — quality is ignored."
    : "Applies to JPEG & WebP only.";

  const chosen = selectedFormat();
  formatHint.textContent = chosen
    ? `Converting to ${FORMAT_LABELS[chosen] || chosen}.`
    : "Keeps the uploaded format.";
}

/* ---------- before / after rendering ---------- */

function showBeforePreview(file) {
  revoke(beforeUrl);
  beforeUrl = URL.createObjectURL(file);

  const img = new Image();
  img.onload = () => {
    beforeDims.textContent = `${img.naturalWidth} × ${img.naturalHeight}`;
    beforeStats.hidden = false;
  };
  img.src = beforeUrl;

  beforePane.innerHTML = "";
  const preview = document.createElement("img");
  preview.src = beforeUrl;
  preview.alt = "Original image preview";
  beforePane.appendChild(preview);

  beforeSize.textContent = formatBytes(file.size);
}

// Draw the Before and After images on ONE shared scale so the resize is
// visible: the larger of the two is fitted to the pane, the other is drawn
// proportionally smaller. Same aspect ratio, so nothing is distorted.
function applyComparisonScale(meta) {
  const beforeImg = beforePane.querySelector("img");
  const afterImg = afterPane.querySelector("img");
  if (!beforeImg || !afterImg) return;

  const boxW = beforePane.clientWidth || afterPane.clientWidth;
  if (!boxW) return;

  const bigW = Math.max(meta.original_width, meta.output_width);
  const bigH = Math.max(meta.original_height, meta.output_height);

  // Fit the larger image into the pane; never enlarge beyond natural pixels.
  const scale = Math.min(boxW / bigW, PANE_MAX_H / bigH, 1);

  const size = (img, w, h) => {
    img.style.width = `${Math.max(1, Math.round(w * scale))}px`;
    img.style.height = `${Math.max(1, Math.round(h * scale))}px`;
  };
  size(beforeImg, meta.original_width, meta.original_height);
  size(afterImg, meta.output_width, meta.output_height);
}

function renderResult(blob, meta) {
  revoke(afterUrl);
  afterUrl = URL.createObjectURL(blob);
  lastMeta = meta;

  afterPane.innerHTML = "";
  const img = document.createElement("img");
  img.src = afterUrl;
  img.alt = "Optimised image preview";
  afterPane.appendChild(img);

  afterSize.textContent = formatBytes(meta.optimized_size);
  afterDims.textContent = `${meta.output_width} × ${meta.output_height}`;

  const positive = meta.savings > 0;
  afterSavings.textContent = positive ? `${meta.savings}%` : "No reduction";
  afterSavings.classList.toggle("is-positive", positive);
  afterStats.hidden = false;

  downloadLink.href = afterUrl;
  downloadLink.download = meta.download_name || "optimised";
  downloadLink.hidden = false;

  applyComparisonScale(meta);
}

/* ---------- optimize request ---------- */

async function runOptimize() {
  if (!currentFile) return;
  clearError();

  afterPane.classList.add("is-loading");
  afterPlaceholder.hidden = true;

  const params = readParams();
  const formData = new FormData();
  formData.append("image", currentFile);
  formData.append("preset", params.preset);
  formData.append("format", params.format);
  formData.append("quality", params.quality);
  formData.append("resize", params.resize);
  formData.append("brightness", params.brightness);
  formData.append("contrast", params.contrast);
  formData.append("sharpen", params.sharpen);
  formData.append("blur", params.blur);
  formData.append("strip", params.strip ? "1" : "0");
  formData.append("orient", params.orient ? "1" : "0");

  let response;
  try {
    response = await fetch("/optimize", { method: "POST", body: formData });
  } catch (_) {
    afterPane.classList.remove("is-loading");
    afterPlaceholder.hidden = false;
    showError("Network error. Please try again.");
    return;
  }

  afterPane.classList.remove("is-loading");

  if (!response.ok) {
    afterPlaceholder.hidden = false;
    let message = `Something went wrong (${response.status}).`;
    try {
      const data = await response.json();
      if (data.error) message = data.error;
    } catch (_) {
      /* non-JSON error */
    }
    showError(message);
    return;
  }

  let meta = {};
  try {
    meta = JSON.parse(response.headers.get("X-Optimize-Meta") || "{}");
  } catch (_) {
    /* header missing/malformed */
  }
  const blob = await response.blob();
  renderResult(blob, meta);
}

/* ---------- file intake ---------- */

function handleFile(file) {
  clearError();

  const ext = extensionOf(file.name);
  if (!ACCEPTED_EXTENSIONS.includes(ext)) {
    showError("Unsupported file type. Please use JPG, PNG or WebP.");
    return;
  }
  if (file.size > MAX_BYTES) {
    showError("File is too large. The maximum size is 25 MB.");
    return;
  }

  currentFile = file;
  syncQualityAvailability();
  updateSummary();
  showBeforePreview(file);
  runOptimize();
}

/* ---------- wiring ---------- */

// Slider drag: update text instantly (cheap). Re-encode only on release.
[
  qualityInput,
  resizeInput,
  brightnessInput,
  contrastInput,
  sharpenInput,
  blurInput,
].forEach((el) => el.addEventListener("input", updateSummary));

// Changing the output format may flip quality on/off (PNG is lossless), so
// keep the quality control in sync before re-encoding.
document.querySelectorAll('input[name="format"]').forEach((el) =>
  el.addEventListener("change", syncQualityAvailability)
);

// A settled change to any control re-runs optimisation (if a file is loaded).
document
  .querySelectorAll(
    'input[name="preset"], input[name="format"], #quality, #resize, ' +
      "#brightness, #contrast, #sharpen, #blur, #strip, #orient"
  )
  .forEach((el) =>
    el.addEventListener("change", () => {
      updateSummary();
      runOptimize();
    })
  );

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fileInput.click();
  }
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) handleFile(fileInput.files[0]);
});

["dragenter", "dragover"].forEach((type) =>
  dropzone.addEventListener(type, (e) => {
    e.preventDefault();
    dropzone.classList.add("is-dragover");
  })
);
["dragleave", "drop"].forEach((type) =>
  dropzone.addEventListener(type, (e) => {
    e.preventDefault();
    dropzone.classList.remove("is-dragover");
  })
);
dropzone.addEventListener("drop", (e) => {
  const files = e.dataTransfer.files;
  if (files.length) {
    fileInput.files = files;
    handleFile(files[0]);
  }
});

// Keep the shared comparison scale correct when the layout reflows.
let resizeRaf = null;
window.addEventListener("resize", () => {
  if (!lastMeta) return;
  cancelAnimationFrame(resizeRaf);
  resizeRaf = requestAnimationFrame(() => applyComparisonScale(lastMeta));
});

// Initial paint.
updateSummary();
