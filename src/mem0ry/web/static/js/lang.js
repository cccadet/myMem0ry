/* Language preference toggle for myMem0ry web UI. */
(function () {
  "use strict";

  function setLang(lang) {
    document.cookie = "lang=" + lang + ";path=/;max-age=31536000;samesite=lax";
    window.location.reload();
  }

  window.setLang = setLang;
})();
