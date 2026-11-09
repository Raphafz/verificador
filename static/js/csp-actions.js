/**
 * Compatibilidade CSP strict — substitui onclick inline por data-csp-*.
 * Carregar com nonce no base.html.
 */
(function () {
  "use strict";

  function runAction(el) {
    var action = el.getAttribute("data-csp-action");
    if (!action) return;
    var arg = el.getAttribute("data-csp-arg");
    switch (action) {
      case "history-back":
        history.back();
        break;
      case "reload":
        location.reload();
        break;
      case "confirm-submit":
        if (confirm(el.getAttribute("data-csp-message") || "Confirmar?")) {
          var form = el.closest("form");
          if (form) form.submit();
        }
        break;
      default:
        if (typeof window[action] === "function") {
          window[action](arg !== null ? arg : undefined);
        }
    }
  }

  document.addEventListener("click", function (ev) {
    var el = ev.target.closest("[data-csp-action]");
    if (!el) return;
    if (el.tagName === "A" && el.getAttribute("href")) return;
    ev.preventDefault();
    runAction(el);
  });

  document.addEventListener("submit", function (ev) {
    var el = ev.target.querySelector("[data-csp-confirm]");
    if (!el) return;
    var msg = el.getAttribute("data-csp-confirm");
    if (!confirm(msg || "Confirmar?")) {
      ev.preventDefault();
    }
  });
})();
