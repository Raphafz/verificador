/**
 * Ativa folhas carregadas com media="print" (substitui onload inline — compatível com CSP strict).
 */
(function () {
  "use strict";

  function activate(link) {
    link.media = "all";
  }

  function initDeferredCss() {
    document.querySelectorAll("link[data-defer-css]").forEach(function (link) {
      if (link.sheet) {
        activate(link);
        return;
      }
      link.addEventListener("load", function () {
        activate(link);
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDeferredCss);
  } else {
    initDeferredCss();
  }
})();
