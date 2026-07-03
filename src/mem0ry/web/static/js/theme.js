/* Theme toggle for myMem0ry web UI — Material Design compliant. */
(function () {
  "use strict";

  function setCookie(name, value) {
    document.cookie = name + "=" + value + ";path=/;max-age=31536000;samesite=lax";
  }

  function setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    setCookie("theme", theme);
  }

  function toggleTheme() {
    var current = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
    setTheme(current === "light" ? "dark" : "light");
    window.location.reload();
  }

  window.setTheme = setTheme;
  window.toggleTheme = toggleTheme;
})();
