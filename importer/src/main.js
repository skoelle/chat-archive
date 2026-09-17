// Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
// Licensed under the MIT License. See LICENSE file in project root for details.

import { invoke } from "@tauri-apps/api/core";

const selected = { instagram: null, facebook: null, "facebook-e2ee": null };
const logEl = document.getElementById("log-output");
const progressEl = document.getElementById("progress");
const importBtn = document.getElementById("btn-import");

function log(msg) {
  logEl.textContent += msg + "\n";
  logEl.scrollTop = logEl.scrollHeight;
}

function setupDropzone(id, platform) {
  const zone = document.getElementById(id);
  const input = document.getElementById(`file-${platform}`);
  zone.addEventListener("click", () => input.click());
  input.addEventListener("change", (e) => handleFiles(e.target.files, platform));
  ["dragenter", "dragover"].forEach((evt) =>
    zone.addEventListener(evt, (e) => { e.preventDefault(); zone.classList.add("dragover"); })
  );
  ["dragleave", "drop"].forEach((evt) =>
    zone.addEventListener(evt, (e) => { e.preventDefault(); zone.classList.remove("dragover"); })
  );
  zone.addEventListener("drop", (e) => handleFiles(e.dataTransfer.files, platform));
}

function handleFiles(fileList, platform) {
  const file = fileList[0];
  if (!file) return;
  selected[platform] = file.path || file.name;
  log(`[${platform}] selected: ${selected[platform]}`);
  importBtn.disabled = !(selected.instagram || selected.facebook || selected["facebook-e2ee"]);
}

function apiConfig() {
  return {
    base_url: document.getElementById("api-url").value,
    token: document.getElementById("api-token").value,
  };
}

document.getElementById("btn-test").addEventListener("click", async () => {
  log("Testing API connection ...");
  try {
    const result = await invoke("test_api_connection", { config: apiConfig() });
    log(`OK: ${result}`);
  } catch (err) {
    log(`Error: ${err}`);
  }
});

document.getElementById("btn-import").addEventListener("click", async () => {
  progressEl.value = 0;
  const config = apiConfig();

  for (const platform of ["instagram", "facebook", "facebook-e2ee"]) {
    const path = selected[platform];
    if (!path) continue;

    log(`--- Starting import: ${platform} ---`);
    try {
      const extracted = await invoke("extract_takeout", { zipPath: path, platform });
      log(`Extracted to: ${extracted}`);

      const result = await invoke("forward_to_api", { extractedPath: extracted, platform, config });
      log(`Sent to API: ${result.threads_sent} threads, ${result.rows_inserted} rows total`);
    } catch (err) {
      log(`Error for ${platform}: ${err}`);
    }
  }
  progressEl.value = 100;
  log("Import complete.");
});

setupDropzone("drop-instagram", "instagram");
setupDropzone("drop-facebook", "facebook");
setupDropzone("drop-facebook-e2ee", "facebook-e2ee");
