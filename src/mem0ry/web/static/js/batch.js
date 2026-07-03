/* Batch selection bar for memory cards. */
(function () {
  "use strict";

  function updateBar() {
    var checked = document.querySelectorAll(".mem-checkbox:checked");
    var bar = document.querySelector("#batch-bar");
    var count = document.querySelector("#batch-count");
    if (!bar || !count) return;

    count.textContent = String(checked.length);
    if (checked.length > 0) {
      bar.classList.add("translate-y-0");
      bar.classList.remove("translate-y-full");
    } else {
      bar.classList.add("translate-y-full");
      bar.classList.remove("translate-y-0");
    }

    document.querySelectorAll(".batch-hidden-id").forEach(function (el) {
      el.remove();
    });

    var deleteForm = document.querySelector("#batch-delete-form");
    var exportForm = document.querySelector("#batch-export-form");
    checked.forEach(function (cb) {
      [deleteForm, exportForm].forEach(function (form) {
        if (!form) return;
        var input = document.createElement("input");
        input.type = "hidden";
        input.name = "ids";
        input.value = cb.value;
        input.className = "batch-hidden-id";
        form.appendChild(input);
      });
    });
  }

  function toggleSelectAll() {
    var all = document.querySelectorAll(".mem-checkbox");
    var checked = document.querySelectorAll(".mem-checkbox:checked");
    var state = checked.length < all.length;
    all.forEach(function (cb) {
      cb.checked = state;
    });
    updateBar();
  }

  document.addEventListener("change", function (e) {
    if (e.target.classList.contains("mem-checkbox")) updateBar();
  });

  window.toggleSelectAll = toggleSelectAll;
  window.updateBar = updateBar;
})();
