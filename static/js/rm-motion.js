/**
 * RM Systems — Motion system v2 (GPU-friendly, vanilla JS)
 */
(function () {
  'use strict';

  var REDUCED =
    window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function initReducedMotion() {
    if (REDUCED) {
      document.body.classList.add('rm-reduced-motion');
    }
  }

  function initRouteEnter() {
    if (REDUCED) return;
    var main = document.getElementById('main-content');
    if (!main) return;
    var target =
      main.querySelector('.saas-page, .rm-dash, .rm-dash-v2, .hub-shell') ||
      main.querySelector('.rm-v2-route-enter');
    if (target && !target.classList.contains('rm-v2-route-enter')) {
      target.classList.add('rm-v2-route-enter');
    }
  }

  function animateCounter(el, target, duration) {
    if (REDUCED) {
      el.textContent = String(target);
      return;
    }
    var start = 0;
    var startTime = null;
    var dur = duration || 680;

    el.classList.add('is-counting');

    function step(ts) {
      if (!startTime) startTime = ts;
      var progress = Math.min((ts - startTime) / dur, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      var value = Math.round(start + (target - start) * eased);
      el.textContent = String(value);
      if (progress < 1) {
        window.requestAnimationFrame(step);
      } else {
        el.classList.remove('is-counting');
      }
    }

    window.requestAnimationFrame(step);
  }

  function initCounters() {
    document.querySelectorAll('[data-rm-counter]').forEach(function (el) {
      var raw = el.getAttribute('data-rm-counter');
      var target = parseInt(raw, 10);
      if (isNaN(target)) return;
      animateCounter(el, target, 720);
    });
  }

  function initStagger() {
    document.querySelectorAll('.rm-stagger').forEach(function (wrap) {
      if (!wrap.dataset.staggerInit) {
        wrap.dataset.staggerInit = '1';
      }
    });
  }

  function initCmdHint() {
    var hint = document.getElementById('rmV2CmdHint');
    if (!hint || REDUCED) return;
    hint.addEventListener('click', function () {
      document.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true })
      );
    });
  }

  function initSidebarCollapse() {
    var btn = document.getElementById('rmV2SidebarCollapse');
    if (!btn) return;

    var storageKey = 'rm-v2-sidebar-collapsed';

    try {
      if (localStorage.getItem(storageKey) === '1') {
        document.body.classList.add('rm-sidebar-collapsed');
      }
    } catch (e) { /* noop */ }

    btn.addEventListener('click', function () {
      document.body.classList.toggle('rm-sidebar-collapsed');
      try {
        localStorage.setItem(
          storageKey,
          document.body.classList.contains('rm-sidebar-collapsed') ? '1' : '0'
        );
      } catch (e) { /* noop */ }
    });
  }

  function initChartTheme() {
    if (typeof window.Chart === 'undefined') return;
    var isDark =
      document.documentElement.getAttribute('data-theme') === 'dark';
    var grid = isDark ? 'rgba(148, 163, 184, 0.12)' : 'rgba(0, 51, 102, 0.08)';
    var text = isDark ? '#94a3b8' : '#64748b';

    window.Chart.defaults.color = text;
    window.Chart.defaults.borderColor = grid;
    window.Chart.defaults.plugins.legend.labels.color = text;

    document.querySelectorAll('canvas').forEach(function (canvas) {
      canvas.classList.add('chart-dark-ready');
    });
  }

  function initFeedback() {
    document.querySelectorAll('.messages .success, .messages .message.success').forEach(function (el) {
      el.classList.add('ds-feedback-success');
    });
    document.querySelectorAll('.messages .error, .messages .message.error').forEach(function (el) {
      el.classList.add('ds-feedback-error');
    });
  }

  function init() {
    initReducedMotion();
    initRouteEnter();
    initCounters();
    initStagger();
    initCmdHint();
    initSidebarCollapse();
    initChartTheme();
    initFeedback();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  document.addEventListener('themeChanged', function () {
    initChartTheme();
  });
})();
