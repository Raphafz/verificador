/**
 * RM Systems — UI premium (motion, sidebar, command palette, partículas)
 * Não altera lógica de negócio — apenas experiência visual
 */
(function () {
  'use strict';

  var REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function initThemeTransition() {
    document.addEventListener('themeChanged', function () {
      var html = document.documentElement;
      html.classList.add('rm-theme-transition');
      window.setTimeout(function () {
        html.classList.remove('rm-theme-transition');
      }, 400);
    });
  }

  var commandPaletteReady = false;

  function initCommandPalette() {
    if (REDUCED_MOTION || commandPaletteReady) {
      return;
    }
    commandPaletteReady = true;

    var palette = document.createElement('div');
    palette.className = 'rm-command-palette';
    palette.setAttribute('role', 'dialog');
    palette.setAttribute('aria-label', 'Paleta de comandos');
    palette.setAttribute('aria-hidden', 'true');
    palette.innerHTML =
      '<div class="rm-command-palette__panel">' +
      '<input type="search" class="rm-command-palette__input" placeholder="Buscar páginas e ações…" autocomplete="off" aria-label="Buscar">' +
      '<ul class="rm-command-palette__results" role="listbox"></ul>' +
      '<p class="rm-command-palette__hint">Pressione <kbd>Esc</kbd> para fechar · <kbd>Ctrl</kbd>+<kbd>K</kbd></p>' +
      '</div>';
    document.body.appendChild(palette);

    var input = palette.querySelector('.rm-command-palette__input');
    var resultsEl = palette.querySelector('.rm-command-palette__results');
    var routes = [];

    try {
      var routesNode = document.getElementById('rm-command-routes');
      if (routesNode && routesNode.textContent) {
        routes = JSON.parse(routesNode.textContent.trim());
      }
    } catch (e) {
      routes = [];
    }

    function renderResults(query) {
      if (!resultsEl) return;
      var q = (query || '').trim().toLowerCase();
      var list = routes.filter(function (r) {
        return !q || (r.label && r.label.toLowerCase().indexOf(q) !== -1);
      });
      if (!list.length) {
        resultsEl.innerHTML = '<li class="rm-command-palette__empty">Nenhum resultado</li>';
        return;
      }
      resultsEl.innerHTML = list
        .map(function (r) {
          var icon = r.icon ? '<i class="fas ' + r.icon + '" aria-hidden="true"></i>' : '';
          return (
            '<li role="option">' +
            '<a href="' + r.url + '" class="rm-command-palette__link">' +
            icon +
            '<span>' + r.label + '</span>' +
            '</a></li>'
          );
        })
        .join('');
    }

    renderResults('');
    input.addEventListener('input', function () {
      renderResults(input.value);
    });

    palette.addEventListener('click', function (e) {
      if (e.target === palette) {
        palette.classList.remove('is-open');
        palette.setAttribute('aria-hidden', 'true');
      }
    });
  }

  function bindCommandPaletteShortcut() {
    if (REDUCED_MOTION) {
      return;
    }
    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        if (!commandPaletteReady) {
          initCommandPalette();
        }
        var palette = document.querySelector('.rm-command-palette');
        if (!palette) {
          return;
        }
        var input = palette.querySelector('.rm-command-palette__input');
        if (palette.classList.contains('is-open')) {
          palette.classList.remove('is-open');
          palette.setAttribute('aria-hidden', 'true');
        } else {
          palette.classList.add('is-open');
          palette.setAttribute('aria-hidden', 'false');
          if (input) {
            input.focus();
          }
        }
      }
      if (e.key === 'Escape') {
        var openPalette = document.querySelector('.rm-command-palette.is-open');
        if (openPalette) {
          openPalette.classList.remove('is-open');
          openPalette.setAttribute('aria-hidden', 'true');
        }
      }
    });
  }

  function enhanceButtons() {
    document.querySelectorAll('.btn-primary, .btn.rm-btn-premium').forEach(function (btn) {
      if (!btn.classList.contains('rm-btn-ripple')) {
        btn.classList.add('rm-btn-ripple');
      }
    });
  }

  function initPageEnter() {
    var main = document.getElementById('main-content');
    if (main && !main.querySelector('.ds-content-enter')) {
      var page = main.querySelector('.saas-page, .rm-dash, .hub-shell, .container-fluid');
      if (page) {
        page.classList.add('ds-content-enter');
      }
    }
  }

  function initTopbarUserMenu() {
    var toggle = document.getElementById('topbarUserMenu');
    var menu = document.querySelector('.topbar-user-menu__dropdown');
    if (!toggle || !menu) return;

    if (typeof window.bootstrap !== 'undefined' && window.bootstrap.Dropdown) {
      var existing = window.bootstrap.Dropdown.getInstance(toggle);
      if (existing) {
        existing.dispose();
      }
      window.bootstrap.Dropdown.getOrCreateInstance(toggle, {
        offset: [0, 8],
        boundary: 'viewport',
        popperConfig: { strategy: 'fixed' }
      });
    }

    if (toggle.dataset.rmMenuBound !== '1') {
      toggle.dataset.rmMenuBound = '1';
      toggle.addEventListener('shown.bs.dropdown', function () {
        menu.querySelectorAll('.dropdown-item').forEach(function (item) {
          item.blur();
        });
      });
    }
  }

  function init() {
    initThemeTransition();
    bindCommandPaletteShortcut();
    initTopbarUserMenu();
    enhanceButtons();
    initPageEnter();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  /* Reinit após scripts/CSS tardios (ex.: remoção de Bootstrap 5.1 duplicado) */
  window.addEventListener('load', function () {
    initTopbarUserMenu();
  });
})();
