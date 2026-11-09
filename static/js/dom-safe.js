/**
 * Helpers DOM seguros (evita XSS via innerHTML com dados do usuário).
 */
(function (global) {
  function appendTextWithBreaks(parent, text) {
    const lines = String(text ?? "").split("\n");
    lines.forEach((line, index) => {
      if (index > 0) {
        parent.appendChild(document.createElement("br"));
      }
      parent.appendChild(document.createTextNode(line));
    });
  }

  function appendTicketMessage(container, msg) {
    if (msg.id != null && container) {
      const existing = container.querySelector(
        '[data-message-id="' + String(msg.id) + '"]'
      );
      if (existing) return existing;
    }

    const messageDiv = document.createElement("div");
    const mine = msg.is_sent_by_me;
    const useNewLayout = container && container.classList.contains("company-tickets-chat__messages");
    if (useNewLayout) {
      messageDiv.className = "company-tickets-chat__message" + (mine ? " company-tickets-chat__message--mine" : "");
    } else {
      messageDiv.className = "message" + (mine ? " sent-by-me" : "");
    }
    if (msg._pending) {
      messageDiv.dataset.pending = "true";
      messageDiv.classList.add("company-tickets-chat__message--pending");
    }
    if (msg.id != null) {
      messageDiv.dataset.messageId = String(msg.id);
    }

    if (useNewLayout) {
      const avatar = document.createElement("span");
      avatar.className = "company-tickets-chat__avatar";
      avatar.setAttribute("aria-hidden", "true");
      const name = msg.sent_by || "?";
      avatar.textContent = name.charAt(0).toUpperCase();
      messageDiv.appendChild(avatar);
      if (msg.sent_by_role === "RM") {
        messageDiv.classList.add("company-tickets-chat__message--rm");
      }
    }

    const wrap = document.createElement("div");
    if (useNewLayout && msg.sent_by_role === "RM") {
      const role = document.createElement("span");
      role.className = "company-tickets-chat__role";
      role.textContent = "Equipe RM Systems";
      wrap.appendChild(role);
    }

    const bubble = document.createElement("div");
    bubble.className = useNewLayout ? "company-tickets-chat__bubble" : "message-bubble";
    appendTextWithBreaks(bubble, msg.message);

    const meta = document.createElement("div");
    meta.className = useNewLayout ? "company-tickets-chat__meta" : "message-meta";
    const author = document.createElement("strong");
    author.textContent = msg.sent_by || "";
    meta.appendChild(author);
    meta.appendChild(document.createTextNode(useNewLayout ? " · " + (msg.created_at || "") : " - " + (msg.created_at || "")));

    wrap.appendChild(bubble);
    wrap.appendChild(meta);
    messageDiv.appendChild(wrap);
    container.appendChild(messageDiv);
    return messageDiv;
  }

  global.RMDomSafe = {
    appendTextWithBreaks,
    appendTicketMessage,
  };
})(typeof window !== "undefined" ? window : globalThis);
