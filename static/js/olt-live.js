/**
 * Operação OLT ao vivo — polling, resumo amigável, log técnico colapsável
 */
(function () {
  'use strict';

  function initOltLive(config) {
    if (!config || !config.statusUrl) return;

    if (window.globalLoadingScreen) {
      window.globalLoadingScreen.forceHide();
    }

    var pre = document.getElementById('liveLogPre');
    var spinner = document.getElementById('jobSpinner');
    var statusLabel = document.getElementById('jobStatusLabel');
    var statusHint = document.getElementById('jobStatusHint');
    var statusBadge = document.getElementById('jobStatusBadge');
    var summaryEl = document.getElementById('jobSummary');
    var summaryPanel = document.getElementById('summaryPanel');
    var resultPanel = document.getElementById('resultPanel');
    var resultTitle = document.getElementById('resultTitle');
    var resultSerials = document.getElementById('resultSerials');
    var resultMessage = document.getElementById('resultMessage');
    var btnCopy = document.getElementById('btnCopyLiveLog');
    var btnStaticLog = document.getElementById('btnStaticLog');
    var btnToggleLog = document.getElementById('btnToggleLog');
    var logWrap = document.getElementById('logWrap');
    var liveShell = document.getElementById('oltLiveShell');
    var pollTimer = null;
    var userScrolledUp = false;

    if (!pre) return;

    if (pre) {
      pre.addEventListener('scroll', function () {
        var nearBottom = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 48;
        userScrolledUp = !nearBottom;
      });
    }

    function scrollToBottom() {
      if (!userScrolledUp && pre) {
        pre.scrollTop = pre.scrollHeight;
      }
    }

    function setBadge(status, running) {
      if (!statusBadge) return;
      statusBadge.className = 'ds-badge ds-badge--' + (status || 'draft');
      if (running) {
        statusBadge.innerHTML =
          '<span class="ds-badge__dot"></span> ' +
          (statusLabel ? statusLabel.textContent : 'Processando');
      } else {
        statusBadge.textContent = statusLabel ? statusLabel.textContent : '';
      }
    }

    function isListOperation(data) {
      return data.operation === 'list';
    }

    function operationDoneTitle(data) {
      var list = isListOperation(data);
      if (data.status === 'failed') {
        return list ? 'Listagem não concluída' : 'Exclusão não concluída';
      }
      return list ? 'Listagem concluída' : 'Exclusão concluída';
    }

    function showDone(data) {
      if (spinner) spinner.classList.add('d-none');
      if (liveShell) liveShell.classList.add('is-done');
      if (btnCopy) btnCopy.disabled = false;
      if (btnStaticLog) btnStaticLog.classList.remove('d-none');

      if (statusHint) {
        statusHint.textContent =
          data.user_hint ||
          (data.status === 'failed' && data.user_summary
            ? data.user_summary
            : 'Operação finalizada.');
      }

      if (data.user_summary && summaryEl && summaryPanel) {
        summaryPanel.classList.remove('d-none');
        summaryEl.textContent = data.user_summary;
        summaryPanel.classList.toggle('is-error', data.status === 'failed');
      }

      setBadge(data.status, false);

      if (!resultPanel) return;
      resultPanel.classList.remove('d-none');

      if (data.serial_count > 0) {
        if (resultTitle) {
          resultTitle.textContent = data.serial_count + ' equipamento(s) encontrado(s)';
        }
        if (resultSerials) {
          resultSerials.value = data.serials;
          resultSerials.classList.remove('d-none');
        }
        if (resultMessage) resultMessage.classList.add('d-none');
        if (data.status === 'ready' && statusHint) {
          statusHint.textContent =
            'Copie os números de série abaixo e cole no painel de exclusão.';
        }
      } else if (data.status === 'done' || data.status === 'failed') {
        if (resultTitle) resultTitle.textContent = operationDoneTitle(data);
        if (resultSerials) resultSerials.classList.add('d-none');
        if (resultMessage) {
          resultMessage.textContent = data.user_summary || data.status_label;
          resultMessage.classList.remove('d-none');
        }
      } else {
        if (resultTitle) resultTitle.textContent = 'Nenhum offline nesta porta';
        if (resultSerials) resultSerials.classList.add('d-none');
        if (resultMessage) {
          resultMessage.textContent = 'Tente outra porta GPON ou confira o log.';
          resultMessage.classList.remove('d-none');
        }
      }
    }

    async function poll() {
      try {
        var res = await fetch(config.statusUrl, {
          credentials: 'same-origin',
          headers: {
            Accept: 'application/json',
            'X-Skip-Global-Loading': '1',
          },
        });
        if (!res.ok) {
          pollTimer = setTimeout(poll, 1500);
          return;
        }
        var data = await res.json();

        if (pre && data.log) {
          pre.textContent = data.log;
        }
        if (statusLabel) {
          statusLabel.textContent = data.user_status_label || data.status_label;
        }
        if (statusHint && data.running && data.user_hint) {
          statusHint.textContent = data.user_hint;
        }
        setBadge(data.status, data.running);
        scrollToBottom();

        if (data.running) {
          if (spinner) spinner.classList.remove('d-none');
          if (btnCopy) btnCopy.disabled = !data.log;
          pollTimer = setTimeout(poll, 450);
        } else {
          showDone(data);
        }
      } catch (err) {
        pollTimer = setTimeout(poll, 1200);
      }
    }

    if (btnCopy) {
      btnCopy.addEventListener('click', function () {
        navigator.clipboard.writeText(pre.textContent || '').then(function () {
          if (typeof showSuccess === 'function') {
            showSuccess('Log copiado para a área de transferência.');
          }
          btnCopy.innerHTML = '<i class="fas fa-check me-1"></i> Copiado';
          setTimeout(function () {
            btnCopy.innerHTML = '<i class="fas fa-copy me-1"></i> Copiar log';
          }, 2000);
        });
      });
    }

    if (btnToggleLog && logWrap) {
      btnToggleLog.addEventListener('click', function () {
        logWrap.classList.toggle('is-collapsed');
        var collapsed = logWrap.classList.contains('is-collapsed');
        btnToggleLog.textContent = collapsed ? 'Mostrar log técnico' : 'Ocultar log técnico';
      });
    }

    poll();
  }

  window.initOltLive = initOltLive;

  document.addEventListener('DOMContentLoaded', function () {
    var shell = document.getElementById('oltLiveShell');
    if (!shell || !shell.dataset.statusUrl) return;
    initOltLive({ statusUrl: shell.dataset.statusUrl });
  });
})();
