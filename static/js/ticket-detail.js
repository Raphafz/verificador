/**
 * Chat do ticket — envio AJAX, polling rápido e UI otimista.
 */
(function () {
  if (window.globalLoadingScreen && typeof window.globalLoadingScreen.forceHide === "function") {
    window.globalLoadingScreen.forceHide();
  }

  const root = document.getElementById("ticketChatRoot");
  if (!root) return;

  const chatMessages = document.getElementById("chatMessages");
  const messageForm = document.getElementById("messageForm");
  const pollUrl = root.dataset.pollUrl || "";
  const POLL_MS = 2000;
  let lastMessageId = parseInt(root.dataset.lastMessageId || "0", 10) || 0;
  let pollTimer = null;
  let sending = false;

  function getCsrfToken() {
    const input = document.querySelector("[name=csrfmiddlewaretoken]");
    if (input && input.value) return input.value;
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function scrollChatToBottom() {
    if (chatMessages) {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  }

  function removeEmptyState() {
    const empty = chatMessages && chatMessages.querySelector(".company-tickets-chat__empty");
    if (empty) empty.remove();
  }

  function messageExists(id) {
    if (!id || !chatMessages) return false;
    return !!chatMessages.querySelector('[data-message-id="' + id + '"]');
  }

  function appendMessages(list) {
    if (!list || !list.length || !chatMessages) return false;
    let added = false;
    list.forEach(function (msg) {
      if (messageExists(msg.id)) return;
      if (window.RMDomSafe && window.RMDomSafe.appendTicketMessage) {
        window.RMDomSafe.appendTicketMessage(chatMessages, msg);
        added = true;
      }
      if (msg.id) {
        lastMessageId = Math.max(lastMessageId, msg.id);
      }
    });
    if (added) {
      removeEmptyState();
      scrollChatToBottom();
    }
    return added;
  }

  function fetchJson(url, options) {
    const headers = Object.assign(
      {
        "X-Skip-Global-Loading": "1",
        "X-Requested-With": "XMLHttpRequest",
      },
      options.headers || {}
    );
    return fetch(url, Object.assign({}, options, { headers: headers })).then(function (r) {
      return r.json().then(function (data) {
        if (!r.ok) {
          const err = new Error(data.error || "Erro na requisição");
          err.data = data;
          throw err;
        }
        return data;
      });
    });
  }

  function pollNewMessages() {
    if (!pollUrl || document.hidden) return Promise.resolve();
    return fetchJson(pollUrl + "?last_message_id=" + lastMessageId, { method: "GET" })
      .then(function (data) {
        if (data.has_new && data.messages && data.messages.length) {
          appendMessages(data.messages);
        }
      })
      .catch(function () {});
  }

  function startPolling() {
    if (!pollUrl) return;
    stopPolling();
    pollTimer = setInterval(pollNewMessages, POLL_MS);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function setSendingState(active) {
    sending = active;
    const btn = messageForm && messageForm.querySelector('button[type="submit"]');
    const field = messageForm && messageForm.querySelector('textarea[name="message"]');
    if (btn) {
      btn.disabled = active;
      btn.classList.toggle("is-sending", active);
      if (active) {
        btn.dataset.originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1" aria-hidden="true"></i> Enviando…';
      } else if (btn.dataset.originalHtml) {
        btn.innerHTML = btn.dataset.originalHtml;
      }
    }
    if (field) field.disabled = active;
  }

  function showFormError(text) {
    let box = messageForm && messageForm.querySelector(".ticket-chat-error");
    if (!box && messageForm) {
      box = document.createElement("div");
      box.className = "text-danger small mt-1 ticket-chat-error";
      messageForm.appendChild(box);
    }
    if (box) box.textContent = text || "";
  }

  function sendMessageAjax(text) {
    return fetchJson(pollUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify({ message: text }),
      credentials: "same-origin",
    });
  }

  if (messageForm) {
    messageForm.addEventListener("submit", function (e) {
      e.preventDefault();
      if (sending) return;

      const field = messageForm.querySelector('textarea[name="message"]');
      const text = field && field.value ? field.value.trim() : "";
      if (!text) {
        showFormError("Digite uma mensagem antes de enviar.");
        if (field) field.focus();
        return;
      }

      showFormError("");
      setSendingState(true);

      const optimistic = {
        id: null,
        message: text,
        sent_by: root.dataset.userName || "Você",
        sent_by_role: root.dataset.userRole || "",
        created_at: "agora",
        is_sent_by_me: true,
        _pending: true,
      };

      removeEmptyState();
      if (window.RMDomSafe && window.RMDomSafe.appendTicketMessage) {
        window.RMDomSafe.appendTicketMessage(chatMessages, optimistic);
        scrollChatToBottom();
      }

      sendMessageAjax(text)
        .then(function (data) {
          if (field) field.value = "";
          const pending = chatMessages && chatMessages.querySelector("[data-pending='true']");
          if (pending) pending.remove();
          if (data.message) {
            appendMessages([data.message]);
          }
          return pollNewMessages();
        })
        .catch(function (err) {
          const pending = chatMessages && chatMessages.querySelector("[data-pending='true']");
          if (pending) pending.remove();
          showFormError((err && err.message) || "Não foi possível enviar. Tente novamente.");
          if (field) field.value = text;
        })
        .finally(function () {
          setSendingState(false);
          if (field) field.focus();
        });
    });

    const field = messageForm.querySelector('textarea[name="message"]');
    if (field) {
      field.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          messageForm.requestSubmit();
        }
      });
    }
  }

  scrollChatToBottom();
  startPolling();
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) {
      stopPolling();
    } else {
      pollNewMessages().finally(startPolling);
    }
  });
  pollNewMessages();
})();
