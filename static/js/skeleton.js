/**
 * Skeleton loading — RM Systems Design System
 */
(function (global) {
  'use strict';

  function skeletonCardHTML() {
    return (
      '<label class="cto-card ds-skeleton-cto-card" aria-hidden="true">' +
      '<div class="ds-skeleton ds-skeleton-cto-icon"></div>' +
      '<div class="ds-skeleton-line ds-skeleton-line--med"></div>' +
      '</label>'
    );
  }

  function skeletonTableRowHTML(cols) {
    const cells = Array.from({ length: cols }, () =>
      '<td><div class="ds-skeleton ds-skeleton-table-cell"></div></td>'
    ).join('');
    return '<tr class="ds-skeleton-row" aria-hidden="true">' + cells + '</tr>';
  }

  const SkeletonUI = {
    renderCTOGrid(container, count) {
      if (!container) return;
      const n = Math.max(3, Math.min(count || 4, 6));
      container.innerHTML = '';
      container.setAttribute('aria-busy', 'true');
      container.classList.add('is-skeleton');
      for (let i = 0; i < n; i++) {
        container.insertAdjacentHTML('beforeend', skeletonCardHTML());
      }
    },

    renderTableBody(tbody, rows, cols) {
      if (!tbody) return;
      const r = Math.max(3, Math.min(rows || 5, 8));
      const c = Math.max(2, cols || tbody.closest('table')?.querySelectorAll('thead th').length || 5);
      tbody.innerHTML = '';
      tbody.setAttribute('aria-busy', 'true');
      tbody.classList.add('is-skeleton');
      for (let i = 0; i < r; i++) {
        tbody.insertAdjacentHTML('beforeend', skeletonTableRowHTML(c));
      }
    },

    clearBusy(el) {
      if (!el) return;
      el.removeAttribute('aria-busy');
      el.classList.remove('is-skeleton');
    },
  };

  global.SkeletonUI = SkeletonUI;
})(typeof window !== 'undefined' ? window : global);
