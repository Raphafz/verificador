/**
 * Filtro configurável pelo painel (uma regra por linha, texto exato na mensagem).
 */
export function shouldForwardAlert(text, cfg) {
  if (cfg.filter_enabled !== true) return true;

  const rules = (cfg.filter_rules || []).map((r) => String(r).trim()).filter(Boolean);
  if (rules.length === 0) return true;

  const normalized = text.replace(/\r\n/g, "\n");
  const test = (rule) => normalized.includes(rule);

  if (cfg.filter_match_all) {
    return rules.every(test);
  }
  return rules.some(test);
}

export function getWhatsAppTargets(cfg) {
  if (cfg.whatsapp_alert_phones?.length > 0) {
    return cfg.whatsapp_alert_phones.map((phone) => `${phone}@s.whatsapp.net`);
  }
  if (cfg.whatsapp_group_jid) return [cfg.whatsapp_group_jid];
  return [];
}

/** Aceita ID com ou sem prefixo -100 (supergrupo). */
export function groupIdsMatch(configured, chatId) {
  const a = String(configured ?? "").trim();
  const b = String(chatId ?? "").trim();
  if (!a) return true;
  if (a === b) return true;
  if (a.startsWith("-100") && b === `-${a.slice(4)}`) return true;
  if (b.startsWith("-100") && a === `-${b.slice(4)}`) return true;
  return false;
}
