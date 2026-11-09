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
