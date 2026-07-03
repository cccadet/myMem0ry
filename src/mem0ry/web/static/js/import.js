/* Import page: drag & drop, file validation and submit feedback. */
(function () {
  "use strict";

  var dropZone = document.querySelector("#drop-zone");
  var fileInput = document.querySelector("#file-input");
  var fileName = document.querySelector("#file-name");
  var importBtn = document.querySelector("#import-btn");
  var form = document.querySelector("#import-form");
  var invalidType = window.IMPORT_INVALID_TYPE || "Only .json files are accepted";
  var importingLabel = window.IMPORT_IMPORTING_LABEL || "Importing...";

  if (!dropZone || !fileInput || !fileName || !importBtn || !form) return;

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  function showFile(file) {
    if (!file.name.endsWith(".json")) {
      fileName.textContent = "warning " + invalidType;
      fileName.classList.add("text-red-500");
      fileName.classList.remove("text-green-600");
      importBtn.disabled = true;
    } else {
      fileName.textContent = "check_circle " + file.name + " (" + formatSize(file.size) + ")";
      fileName.classList.add("text-green-600");
      fileName.classList.remove("text-red-500");
      importBtn.disabled = false;
    }
    fileName.classList.remove("hidden");
  }

  dropZone.addEventListener("click", function () {
    fileInput.click();
  });

  dropZone.addEventListener("dragover", function (e) {
    e.preventDefault();
    dropZone.classList.add("border-primary-500", "bg-primary-50");
  });

  dropZone.addEventListener("dragleave", function (e) {
    e.preventDefault();
    dropZone.classList.remove("border-primary-500", "bg-primary-50");
  });

  dropZone.addEventListener("drop", function (e) {
    e.preventDefault();
    dropZone.classList.remove("border-primary-500", "bg-primary-50");
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      showFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", function () {
    if (fileInput.files.length) showFile(fileInput.files[0]);
  });

  form.addEventListener("submit", function () {
    importBtn.disabled = true;
    importBtn.innerHTML = '<span class="material-icons-outlined animate-spin text-base">refresh</span> ' + importingLabel;
  });
})();
