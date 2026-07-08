"use strict";

const ACCEPTED_EXTENSIONS = ["jpg", "jpeg", "png", "webp"];
const MAX_BYTES = 25 * 1024 * 1024;

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const errorEl = document.getElementById("error");

const beforePane = document.getElementById("before-pane");
const beforeStats = document.getElementById("before-stats");
const beforeSize = document.getElementById("before-size");
const beforeDims = document.getElementById("before-dims");

const afterPane = document.getElementById("after-pane");
const afterPlaceholder = document.getElementById("after-placeholder");
const afterStats = document.getElementById("after-stats");
const afterSize = document.getElementById("after-size");
const afterSavings = document.getElementById("after-savings");
const downloadLink = document.getElementById("download-link");

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

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
}

function clearError() {
  errorEl.hidden = true;
  errorEl.textContent = "";
}

function extensionOf(name) {
  return name.includes(".") ? name.split(".").pop().toLowerCase() : "";
}

function resetAfterPane() {
  afterPane.classList.remove("is-loading");
  afterStats.hidden = true;
  downloadLink.hidden = true;
  afterPlaceholder.hidden = false;
  afterPlaceholder.textContent = "The optimised image will appear here.";
  if (!afterPane.contains(afterPlaceholder)) {
    afterPane.innerHTML = "";
    afterPane.appendChild(afterPlaceholder);
  }
}

function showBeforePreview(file) {
  const url = URL.createObjectURL(file);
  const img = new Image();
  img.onload = () => {
    beforeDims.textContent = `${img.naturalWidth} × ${img.naturalHeight}`;
    beforeStats.hidden = false;
  };
  img.src = url;

  beforePane.innerHTML = "";
  const preview = document.createElement("img");
  preview.src = url;
  preview.alt = "Original image preview";
  beforePane.appendChild(preview);

  beforeSize.textContent = formatBytes(file.size);
}

async function optimize(file) {
  afterPane.classList.add("is-loading");
  afterPlaceholder.hidden = true;

  const formData = new FormData();
  formData.append("image", file);

  let response;
  try {
    response = await fetch("/optimize", { method: "POST", body: formData });
  } catch (_) {
    afterPane.classList.remove("is-loading");
    afterPlaceholder.hidden = false;
    showError("Network error. Please try again.");
    return;
  }

  let data = {};
  try {
    data = await response.json();
  } catch (_) {
    /* non-JSON response */
  }

  afterPane.classList.remove("is-loading");

  if (!response.ok) {
    afterPlaceholder.hidden = false;
    showError(data.error || `Something went wrong (${response.status}).`);
    return;
  }

  renderResult(data);
}

function renderResult(data) {
  afterPane.innerHTML = "";
  const img = document.createElement("img");
  img.src = data.preview_url;
  img.alt = "Optimised image preview";
  afterPane.appendChild(img);

  afterSize.textContent = formatBytes(data.optimized_size);

  const positive = data.savings > 0;
  afterSavings.textContent = positive
    ? `${data.savings}%`
    : "Already optimised";
  afterSavings.classList.toggle("is-positive", positive);

  afterStats.hidden = false;

  downloadLink.href = data.download_url;
  downloadLink.hidden = false;
}

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

  resetAfterPane();
  showBeforePreview(file);
  optimize(file);
}

/* --- Drag & drop wiring --- */

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
    fileInput.files = files; // keep the input in sync
    handleFile(files[0]);
  }
});
