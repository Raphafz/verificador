/**
 * UX Forms — loading em submits, confirmações amigáveis
 * (toasts Django: apenas static/js/toast.js)
 */
(function () {
  'use strict';

  function setButtonLoading(btn, loading, label) {
    if (!btn) return;
    if (loading) {
      if (!btn.dataset.uxOriginalHtml) {
        btn.dataset.uxOriginalHtml = btn.innerHTML;
      }
      btn.classList.add('is-loading');
      btn.disabled = true;
      btn.innerHTML =
        '<span class="ds-btn__spinner" aria-hidden="true"></span> ' +
        (label || 'Processando…');
    } else {
      btn.classList.remove('is-loading');
      btn.disabled = false;
      if (btn.dataset.uxOriginalHtml) {
        btn.innerHTML = btn.dataset.uxOriginalHtml;
      }
    }
  }

  function bindFormSubmitLoading() {
    document.querySelectorAll('form[method="post"]:not([data-no-submit-loading])').forEach(function (form) {
      if (form.dataset.uxBound) return;
      form.dataset.uxBound = '1';
      form.addEventListener('submit', function (e) {
        var submitter = e.submitter;
        var btn = submitter && submitter.tagName === 'BUTTON' ? submitter : form.querySelector('[type="submit"]');
        var msg = form.getAttribute('data-loading-message') || 'Enviando…';
        if (btn && !btn.disabled) {
          setButtonLoading(btn, true, msg);
        }
        if (window.globalLoadingScreen && !window.__DISABLE_GLOBAL_LOADING__) {
          var overlayMsg = form.getAttribute('data-overlay-message');
          if (overlayMsg) {
            globalLoadingScreen.showManual(overlayMsg);
          }
        }
      });
    });
  }

  function bindConfirmDialogs() {
    document.querySelectorAll('[data-confirm]:not(form)').forEach(function (el) {
      if (el.dataset.uxConfirmClickBound) return;
      el.dataset.uxConfirmClickBound = '1';
      el.addEventListener('click', function (e) {
        var msg = el.getAttribute('data-confirm');
        if (msg && !window.confirm(msg)) {
          e.preventDefault();
          e.stopPropagation();
        }
      });
    });
    document.querySelectorAll('form[data-confirm]').forEach(function (form) {
      if (form.dataset.uxConfirmSubmitBound) return;
      form.dataset.uxConfirmSubmitBound = '1';
      form.addEventListener('submit', function (e) {
        if (e.defaultPrevented) return;
        var msg = form.getAttribute('data-confirm');
        if (msg && !window.confirm(msg)) {
          e.preventDefault();
          e.stopPropagation();
          var btn = form.querySelector('[type="submit"]');
          setButtonLoading(btn, false);
          if (window.globalLoadingScreen && window.globalLoadingScreen.hideManual) {
            window.globalLoadingScreen.hideManual();
          }
        }
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    bindConfirmDialogs();
    bindFormSubmitLoading();
  });
})();
