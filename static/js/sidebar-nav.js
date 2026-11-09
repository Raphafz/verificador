/**
 * Menu lateral global (hamburger) — RM Systems
 * Sempre em modo overlay: conteúdo centralizado + blur no fundo ao abrir.
 */
(function () {
  'use strict';

  function initSidebarNav() {
    const toggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');

    if (!toggle || !sidebar || !overlay) {
      return;
    }

    function setOpen(open) {
      sidebar.classList.toggle('show', open);
      document.body.classList.toggle('sidebar-open', open);
      document.body.classList.remove('sidebar-collapsed');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.setAttribute('aria-label', open ? 'Fechar menu lateral' : 'Abrir menu lateral');
      overlay.classList.toggle('show', open);
      if (open) {
        document.body.style.overflow = 'hidden';
      } else {
        document.body.style.overflow = '';
        document.body.style.overflowX = 'hidden';
      }
    }

    function close() {
      setOpen(false);
    }

    toggle.setAttribute('aria-controls', 'sidebar');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-label', 'Abrir menu de navegação');

    toggle.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      setOpen(!sidebar.classList.contains('show'));
    });

    overlay.addEventListener('click', close);

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && sidebar.classList.contains('show')) {
        close();
      }
    });

    sidebar.querySelectorAll('.nav-link').forEach(function (link) {
      link.addEventListener('click', function () {
        close();
      });
    });

    var isV2 = document.body.classList.contains('rm-ui-v2');
    var isDesktop = window.matchMedia('(min-width: 992px)').matches;

    if (isV2 && isDesktop) {
      /* V2 desktop: sidebar persistente; collapse via rm-motion.js */
      sidebar.classList.add('show');
      setOpen(false);
    } else {
      /* Overlay mobile / legado */
      try {
        localStorage.removeItem('rm-sidebar-collapsed');
      } catch (e) { /* noop */ }
      document.body.classList.remove('sidebar-collapsed');
      setOpen(false);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSidebarNav);
  } else {
    initSidebarNav();
  }
})();
