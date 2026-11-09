/**
 * Formulário RM — criar/editar empresa (módulos, plano, CNPJ, telefone).
 */
(function () {
  const PLAN_HINTS = {
    P: ["3 usuários", "15 mapas", "500 viab./mês", "Verificador"],
    M: ["8 usuários", "40 mapas", "2.000 viab./mês", "Verificador"],
    G: ["15 usuários", "80 mapas", "8.000 viab./mês", "Verificador + Alertas"],
    XL: ["40 usuários", "200 mapas", "25.000 viab./mês", "Todos os módulos"],
  };

  function syncModuleCards() {
    document.querySelectorAll(".rm-module-card").forEach(function (card) {
      const input = card.querySelector('input[type="checkbox"]');
      if (input) {
        card.classList.toggle("is-checked", input.checked);
        card.setAttribute("aria-checked", input.checked ? "true" : "false");
      }
    });
  }

  function initModuleCards() {
    document.querySelectorAll(".rm-module-card").forEach(function (card) {
      const input = card.querySelector('input[type="checkbox"]');
      if (!input) return;

      input.addEventListener("change", syncModuleCards);

      card.addEventListener("keydown", function (e) {
        if (e.key !== " " && e.key !== "Enter") return;
        e.preventDefault();
        if (!input.disabled) {
          input.checked = !input.checked;
          input.dispatchEvent(new Event("change", { bubbles: true }));
        }
      });
    });
    syncModuleCards();
  }

  function renderPlanHint() {
    const planSelect = document.getElementById("id_plan_code");
    const planHint = document.getElementById("planLimitsHint");
    if (!planSelect || !planHint) return;
    const chips = PLAN_HINTS[planSelect.value] || [];
    planHint.innerHTML = chips
      .map(function (t) {
        return '<span class="rm-form-plan-chip">' + t + "</span>";
      })
      .join("");
  }

  function initPlanSelect() {
    const planSelect = document.getElementById("id_plan_code");
    if (!planSelect) return;
    planSelect.addEventListener("change", renderPlanHint);
    renderPlanHint();
  }

  function initCnpj() {
    const cnpjInput = document.getElementById("id_cnpj");
    if (!cnpjInput) return;

    const formatCnpj = function (raw) {
      const digits = (raw || "").replace(/\D/g, "").slice(0, 14);
      if (!digits) return "";
      if (digits.length <= 2) return digits;
      if (digits.length <= 5) return digits.slice(0, 2) + "." + digits.slice(2);
      if (digits.length <= 8) {
        return digits.slice(0, 2) + "." + digits.slice(2, 5) + "." + digits.slice(5);
      }
      if (digits.length <= 12) {
        return (
          digits.slice(0, 2) +
          "." +
          digits.slice(2, 5) +
          "." +
          digits.slice(5, 8) +
          "/" +
          digits.slice(8)
        );
      }
      return (
        digits.slice(0, 2) +
        "." +
        digits.slice(2, 5) +
        "." +
        digits.slice(5, 8) +
        "/" +
        digits.slice(8, 12) +
        "-" +
        digits.slice(12)
      );
    };

    const enforceCnpj = function () {
      cnpjInput.value = formatCnpj(cnpjInput.value);
      const digits = cnpjInput.value.replace(/\D/g, "");
      cnpjInput.setCustomValidity(
        digits && digits.length !== 14 ? "CNPJ deve conter 14 dígitos." : ""
      );
    };
    cnpjInput.addEventListener("input", enforceCnpj);
    cnpjInput.addEventListener("blur", enforceCnpj);
    enforceCnpj();
  }

  function initPhone() {
    const phoneInput = document.getElementById("id_phone");
    if (!phoneInput) return;

    const formatPhone = function (raw) {
      const digits = (raw || "").replace(/\D/g, "").slice(0, 11);
      if (!digits) return "";
      if (digits.length <= 2) return "(" + digits;
      if (digits.length <= 6) {
        return "(" + digits.slice(0, 2) + ") " + digits.slice(2);
      }
      if (digits.length <= 10) {
        return (
          "(" +
          digits.slice(0, 2) +
          ") " +
          digits.slice(2, 6) +
          "-" +
          digits.slice(6)
        );
      }
      return (
        "(" +
        digits.slice(0, 2) +
        ") " +
        digits.slice(2, 7) +
        "-" +
        digits.slice(7)
      );
    };

    const enforcePhone = function () {
      phoneInput.value = formatPhone(phoneInput.value);
      const digits = phoneInput.value.replace(/\D/g, "");
      phoneInput.setCustomValidity(
        digits && ![10, 11].includes(digits.length) ? "Telefone inválido." : ""
      );
    };
    phoneInput.addEventListener("input", enforcePhone);
    phoneInput.addEventListener("blur", enforcePhone);
    enforcePhone();
  }

  function init() {
    initModuleCards();
    initPlanSelect();
    initCnpj();
    initPhone();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
