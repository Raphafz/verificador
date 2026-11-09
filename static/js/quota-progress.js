/**
 * Barras de quota — largura dinâmica via JS (evita style="" inline bloqueado pelo CSP).
 */
(function () {
  "use strict";

  function initQuotaProgress() {
    document.querySelectorAll(".rm-quota-panel__progress-fill[data-pct]").forEach(function (el) {
      var used = parseInt(el.getAttribute("data-used"), 10) || 0;
      var pct = parseFloat(el.getAttribute("data-pct")) || 0;
      if (used > 0 && pct < 4) {
        pct = 4;
      }
      el.style.width = pct + "%";
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initQuotaProgress);
  } else {
    initQuotaProgress();
  }
})();
