import "dotenv/config";

function optional(name, fallback = "") {
  return process.env[name]?.trim() || fallback;
}

function required(name) {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`Variável obrigatória ausente no .env: ${name}`);
  }
  return value;
}

function parsePhones(raw) {
  if (!raw?.trim()) return [];
  return raw
    .split(",")
    .map((p) => p.replace(/\D/g, ""))
    .filter(Boolean);
}

function parseLinks(raw) {
  if (!raw?.trim()) {
    return ["LINK.K2", "LINK.INOVA.VIA.INOVA"];
  }
  return raw.split(",").map((s) => s.trim()).filter(Boolean);
}

const alertFilterEnv = process.env.ALERT_FILTER_ENABLED?.trim().toLowerCase();
const antibanEnv = process.env.ANTIBAN_ENABLED?.trim().toLowerCase();

function intEnv(name, fallback) {
  const n = parseInt(process.env[name], 10);
  return Number.isFinite(n) && n >= 0 ? n : fallback;
}

function parsePairingPhone(raw) {
  if (!raw?.trim()) return null;
  const digits = raw.replace(/\D/g, "");
  return digits || null;
}

const loginMode = process.env.WHATSAPP_LOGIN_MODE?.trim().toLowerCase();

export const config = {
  /** Modo legado (index.js); no SaaS o token vem da API Django por empresa. */
  telegramToken: optional("TELEGRAM_BOT_TOKEN"),
  telegramGroupId: process.env.TELEGRAM_GROUP_ID?.trim() || null,
  whatsappGroupJid: process.env.WHATSAPP_GROUP_JID?.trim() || null,
  /** qr = escanear QR | pairing = código de 8 letras no app */
  whatsappLoginMode: loginMode === "pairing" ? "pairing" : "qr",
  /** Número da conta WhatsApp que conecta (DDI+DDD+número, só dígitos) */
  whatsappPairingPhone: parsePairingPhone(process.env.WHATSAPP_PAIRING_PHONE),
  whatsappAlertPhones: parsePhones(process.env.WHATSAPP_ALERT_PHONES),
  messagePrefix: process.env.MESSAGE_PREFIX?.trim() || "[TG]",
  /** true = só LINK.K2 e LINK.INOVA com evento de largura de banda */
  alertFilterEnabled: alertFilterEnv !== "false" && alertFilterEnv !== "0",
  alertLinks: parseLinks(process.env.ALERT_LINKS),
  alertEventKeyword:
    process.env.ALERT_EVENT_KEYWORD?.trim() ||
    "Alto uso de largura de banda (>4.5%)",
  antibanEnabled: antibanEnv !== "false" && antibanEnv !== "0",
  antibanDelayMinMs: intEnv("ANTIBAN_DELAY_MIN_MS", 1000),
  antibanDelayMaxMs: intEnv("ANTIBAN_DELAY_MAX_MS", 6000),
  antibanDelayBetweenTargetsMs: intEnv("ANTIBAN_DELAY_BETWEEN_TARGETS_MS", 2000),
  antibanWarmupSec: intEnv("ANTIBAN_WARMUP_SEC", 60),
};

export function getWhatsAppTargets() {
  if (config.whatsappAlertPhones.length > 0) {
    return config.whatsappAlertPhones.map((phone) => `${phone}@s.whatsapp.net`);
  }
  if (config.whatsappGroupJid) {
    return [config.whatsappGroupJid];
  }
  return [];
}
