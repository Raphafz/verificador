/**
 * Formulários de autenticação (login, reset de senha) — toggles e UX.
 */
(function () {
  "use strict";

  function bindPasswordToggles() {
    document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
      if (button.dataset.bound === "1") return;
      button.dataset.bound = "1";
      button.addEventListener("click", function () {
        var inputId = button.getAttribute("data-password-toggle");
        var input = inputId ? document.getElementById(inputId) : null;
        if (!input) return;
        var icon = button.querySelector("i");
        var show = input.type === "password";
        input.type = show ? "text" : "password";
        if (icon) {
          icon.classList.toggle("fa-eye", !show);
          icon.classList.toggle("fa-eye-slash", show);
        }
        button.setAttribute(
          "aria-label",
          show ? "Ocultar senha" : "Mostrar senha"
        );
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindPasswordToggles);
  } else {
    bindPasswordToggles();
  }
})();
