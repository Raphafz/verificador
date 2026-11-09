/**
 * Histórico de busca FTTH — sessionStorage, TTL, sem endereço completo (LGPD).
 */
(function (global) {
  const STORAGE_KEY = 'ftth_search_history_v2';
  const DEFAULT_TTL_MIN = 30;
  const DEFAULT_MAX = 8;

  function config() {
    return {
      enabled: global.FTTH_SEARCH_HISTORY_ENABLED !== false,
      ttlMinutes: Number(global.FTTH_SEARCH_HISTORY_TTL_MINUTES) || DEFAULT_TTL_MIN,
      maxItems: Number(global.FTTH_SEARCH_HISTORY_MAX_ITEMS) || DEFAULT_MAX,
    };
  }

  function hashQuery(query) {
    const q = String(query || '').trim().toLowerCase();
    let h = 0;
    for (let i = 0; i < q.length; i++) {
      h = (h * 31 + q.charCodeAt(i)) >>> 0;
    }
    return h.toString(16);
  }

  function sanitizeLabel(query) {
    const parts = String(query || '').split(',').map((p) => p.trim()).filter(Boolean);
    if (parts.length >= 2) {
      return parts.slice(-2).join(', ').slice(0, 80);
    }
    const words = String(query || '').trim().split(/\s+/);
    if (words.length > 3) {
      return words.slice(0, 2).join(' ') + '…';
    }
    return String(query || '').trim().slice(0, 40);
  }

  function loadRaw() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      const data = JSON.parse(raw);
      return Array.isArray(data.items) ? data.items : [];
    } catch (_) {
      return [];
    }
  }

  function saveRaw(items) {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ items, savedAt: Date.now() }));
    } catch (_) { /* quota */ }
  }

  function purgeExpired(items, ttlMs) {
    const now = Date.now();
    return items.filter((it) => it && it.ts && now - it.ts < ttlMs);
  }

  const SearchHistorySafe = {
    isEnabled() {
      return config().enabled;
    },

    load() {
      if (!this.isEnabled()) return [];
      const { ttlMinutes, maxItems } = config();
      const ttlMs = ttlMinutes * 60 * 1000;
      let items = purgeExpired(loadRaw(), ttlMs);
      items = items.slice(-maxItems);
      saveRaw(items);
      return items;
    },

    add(query) {
      if (!this.isEnabled() || !query || String(query).trim().length < 2) return;
      const { ttlMinutes, maxItems } = config();
      const ttlMs = ttlMinutes * 60 * 1000;
      const clean = String(query).trim();
      const h = hashQuery(clean);
      let items = purgeExpired(loadRaw(), ttlMs);
      items = items.filter((it) => it.h !== h);
      items.push({
        h,
        label: sanitizeLabel(clean),
        ts: Date.now(),
      });
      items = items.slice(-maxItems);
      saveRaw(items);
      return items;
    },

    clear() {
      try {
        sessionStorage.removeItem(STORAGE_KEY);
      } catch (_) { /* ignore */ }
    },

    /** Compatível com UI que espera { query } */
    toDisplayList(items) {
      return (items || []).map((it) => ({ query: it.label, _hash: it.h }));
    },
  };

  global.SearchHistorySafe = SearchHistorySafe;
})(typeof window !== 'undefined' ? window : global);
