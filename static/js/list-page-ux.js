/**
 * UX em listagens (mapas, usuários): skeleton em ações async + toasts padronizados
 */
(function () {
  'use strict';

  function notify(message, type) {
    if (typeof window.showError === 'function' && type === 'error') {
      window.showError(message);
      return;
    }
    if (typeof window.showSuccess === 'function' && type === 'success') {
      window.showSuccess(message);
      return;
    }
    if (typeof window.showWarning === 'function' && type === 'warning') {
      window.showWarning(message);
      return;
    }
    if (typeof window.toastManager !== 'undefined') {
      window.toastManager.show(message, type || 'info');
      return;
    }
    alert(message);
  }

  function tableWrap(table) {
    return table.closest('.ds-table-wrap') || table.parentElement;
  }

  function showTableLoading(table) {
    const tbody = table.querySelector('tbody');
    if (!tbody || !window.SkeletonUI) return null;
    const original = tbody.innerHTML;
    const cols = table.querySelectorAll('thead th').length || 5;
    window.SkeletonUI.renderTableBody(tbody, 5, cols);
    table.setAttribute('aria-busy', 'true');
    return { tbody, original };
  }

  function hideTableLoading(table, state) {
    if (!table || !state) return;
    table.removeAttribute('aria-busy');
    if (state.tbody) {
      state.tbody.innerHTML = state.original;
      window.SkeletonUI?.clearBusy(state.tbody);
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!document.querySelector('.js-delete-map')) {
      return;
    }
    document.querySelectorAll('.js-delete-map').forEach(function (btn) {
      if (btn.dataset.uxBound === '1') return;
      btn.dataset.uxBound = '1';

      btn.addEventListener('click', async function () {
        const table = btn.closest('table');
        const confirmed = confirm('Excluir este mapa? Esta ação não pode ser desfeita.');
        if (!confirmed) return;

        const id = btn.getAttribute('data-map-id');
        const base = btn.getAttribute('data-delete-url');
        if (!base || !id) return;

        const url = base.replace('/0/', '/' + id + '/');
        const state = table ? showTableLoading(table) : null;
        btn.disabled = true;

        try {
          const csrftoken = document.cookie
            .split('; ')
            .find(function (r) { return r.startsWith('csrftoken='); })
            ?.split('=')[1];

          const resp = await fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrftoken || '' },
          });
          const data = await resp.json().catch(function () { return {}; });

          if (data.success) {
            notify('Mapa excluído com sucesso.', 'success');
            setTimeout(function () { location.reload(); }, 400);
          } else {
            notify(data.message || 'Não foi possível excluir o mapa.', 'error');
            hideTableLoading(table, state);
            btn.disabled = false;
          }
        } catch (e) {
          notify('Erro de conexão. Tente novamente.', 'error');
          hideTableLoading(table, state);
          btn.disabled = false;
        }
      });
    });

    document.querySelectorAll('.js-download-map').forEach(function (link) {
      if (link.dataset.uxBound === '1') return;
      link.dataset.uxBound = '1';

      link.addEventListener('click', function () {
        const original = link.innerHTML;
        link.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Baixando…';
        link.style.pointerEvents = 'none';
        notify('Preparando download…', 'info');
        setTimeout(function () {
          link.innerHTML = original;
          link.style.pointerEvents = 'auto';
        }, 8000);
      });
    });

    document.querySelectorAll('form[data-loading-message]').forEach(function (form) {
      if (form.dataset.uxFormBound === '1') return;
      form.dataset.uxFormBound = '1';
      form.addEventListener('submit', function () {
        const msg = form.getAttribute('data-loading-message') || 'Salvando…';
        if (window.loadingManager) {
          window.loadingManager.showFormLoading(form.id || 'form-' + Date.now(), { text: msg });
        } else if (window.globalLoadingScreen) {
          window.globalLoadingScreen.forceShow(msg);
        }
      });
    });
  });
})();
