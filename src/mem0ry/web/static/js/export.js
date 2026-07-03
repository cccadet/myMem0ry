/* Export page: enable buttons when checkboxes are selected. */
(function () {
  "use strict";

  function updateButton(groupName, buttonId) {
    var checked = document.querySelectorAll('input[name="' + groupName + '"]:checked');
    var btn = document.querySelector("#" + buttonId);
    if (btn) btn.disabled = checked.length === 0;
  }

  var scopeCheckboxes = document.querySelectorAll('input[name="scopes"]');
  var projectCheckboxes = document.querySelectorAll('input[name="project_ids"]');

  scopeCheckboxes.forEach(function (cb) {
    cb.addEventListener("change", function () {
      updateButton("scopes", "scope-export-btn");
    });
  });

  projectCheckboxes.forEach(function (cb) {
    cb.addEventListener("change", function () {
      updateButton("project_ids", "project-export-btn");
    });
  });

  var exportForm = document.querySelector("#export-form");
  if (exportForm) {
    exportForm.addEventListener("submit", function (e) {
      var btn = e.submitter;
      if (btn) {
        btn.innerHTML = '<span class="material-icons-outlined animate-spin text-base">refresh</span> ' + (window.EXPORT_EXPORTING_LABEL || "Exporting...");
        btn.disabled = true;
      }
    });
  }
})();
