/**
 * Bridge SaaS multi-empresa e multi-linha WhatsApp.
 */
import "./env-bootstrap.js";
import { Telegraf } from "telegraf";
import { loadBridgeConfigsFromSaas } from "./load-from-api.js";
import {
  ensureSessionForLine,
  getSessionStatus,
  hasSavedAuth,
  lineSessionKey,
  resolveSenderSessionKeys,
  isSessionReady,
} from "./whatsapp-saas.js";
import { startWhatsappApiServer } from "./whatsapp-api.js";
import { scheduleWhatsAppSend } from "./antiban-saas.js";
import { shouldForwardAlert, getWhatsAppTargets, groupIdsMatch } from "./filters-saas.js";

const CONFIG_RELOAD_MS = parseInt(process.env.ALERT_BRIDGE_RELOAD_MS || "15000", 10);

const liveConfigs = new Map();
const botsBySlug = new Map();

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function formatMessage(cfg, from, text) {
  if (from?.is_bot) return text;
  const parts = [from?.first_name, from?.last_name].filter(Boolean);
  const name = parts.join(" ").trim() || from?.username || `id${from?.id}`;
  const prefix = cfg.message_prefix || "[TG]";
  return `${prefix} ${name}\n${text}`;
}

async function ensureSendersReady(cfg) {
  const slug = cfg.company_slug;
  const ready = resolveSenderSessionKeys(cfg).filter((sk) => isSessionReady(sk));
  if (ready.length > 0) return ready;

  for (const line of cfg.whatsapp_lines || []) {
    const sk = lineSessionKey(slug, line.line_id);
    if (!hasSavedAuth(sk)) continue;
    const st = getSessionStatus(sk);
    if (st?.status === "disconnected" || st?.status === "error") continue;
    try {
      await ensureSessionForLine(line, slug);
    } catch (err) {
      console.error(`[${sk}]`, err.message);
    }
  }

  return resolveSenderSessionKeys(cfg).filter((sk) => isSessionReady(sk));
}

function startBotForConfig(cfg) {
  liveConfigs.set(cfg.company_slug, cfg);
  if (botsBySlug.has(cfg.company_slug)) {
    return botsBySlug.get(cfg.company_slug);
  }

  const bot = new Telegraf(cfg.telegram_token);
  const slug = cfg.company_slug;

  bot.on("message", async (ctx) => {
    const current = liveConfigs.get(slug);
    if (!current) return;

    const chat = ctx.chat;
    if (!chat || chat.type === "private") return;

    const text = ctx.message.text ?? ctx.message.caption ?? null;
    if (!text) return;

    if (!shouldForwardAlert(text, current)) {
      console.log(`[${slug}] Mensagem ignorada (filtro ativo).`);
      return;
    }

    if (current.telegram_group_id && !groupIdsMatch(current.telegram_group_id, chat.id)) {
      return;
    }

    if (!current.telegram_group_id) {
      console.log(`[${slug}] Grupo "${chat.title}" → TELEGRAM_GROUP_ID=${chat.id}`);
    }

    const jids = getWhatsAppTargets(current);
    if (jids.length === 0) {
      console.log(`[${slug}] Sem destino WhatsApp (telefone/JID).`);
      return;
    }

    const keys = await ensureSendersReady(current);
    if (keys.length === 0) {
      console.log(
        `[${slug}] Chip WhatsApp não conectado — /${slug}/alertas/config/`
      );
      return;
    }

    const body = formatMessage(current, ctx.from, text);
    for (const sk of keys) {
      try {
        await scheduleWhatsAppSend(sk, jids, body, current);
        console.log(`[${slug}] Telegram → WhatsApp via ${sk}`);
      } catch (err) {
        console.error(`[${slug}] ${sk}:`, err.message);
      }
    }
  });

  bot.launch();
  console.log(`[${slug}] Telegram ativo (${cfg.company_name})`);
  botsBySlug.set(slug, bot);
  return bot;
}

async function refreshLiveConfigs() {
  try {
    const configs = await loadBridgeConfigsFromSaas();
    if (!configs?.length) return;
    for (const cfg of configs) {
      liveConfigs.set(cfg.company_slug, cfg);
      if (!botsBySlug.has(cfg.company_slug)) {
        startBotForConfig(cfg);
        console.log(`[${cfg.company_slug}] Bot Telegram registrado.`);
      }
    }
  } catch (err) {
    console.error("Reload config SaaS:", err.message);
  }
}

async function waitForConfigs() {
  const url = process.env.ALERT_BRIDGE_API_URL;
  const token = process.env.ALERT_BRIDGE_API_TOKEN;
  if (!url || !token) {
    console.error("Defina ALERT_BRIDGE_API_URL e ALERT_BRIDGE_API_TOKEN.");
    process.exit(1);
  }

  while (true) {
    try {
      const configs = await loadBridgeConfigsFromSaas();
      if (configs?.length) return configs;
      console.log("Aguardando bridge ativo em /{slug}/alertas/config/");
    } catch (err) {
      console.error("API SaaS:", err.message);
    }
    await sleep(15000);
  }
}

async function bootWhatsappSessions(configs) {
  for (const cfg of configs) {
    for (const line of cfg.whatsapp_lines || []) {
      const sk = lineSessionKey(cfg.company_slug, line.line_id);
      const st = getSessionStatus(sk);
      if (st?.status === "disconnected" || st?.status === "error") continue;
      if (!hasSavedAuth(sk)) {
        console.log(`[${sk}] Conecte em /${cfg.company_slug}/alertas/config/`);
        continue;
      }
      try {
        await ensureSessionForLine(line, cfg.company_slug);
      } catch (err) {
        console.error(`[${sk}]`, err.message);
      }
    }
  }
}

console.log("=== RM Alert Bridge (multi-linha WhatsApp) ===\n");
startWhatsappApiServer();

const configs = await waitForConfigs();
await bootWhatsappSessions(configs);
configs.forEach(startBotForConfig);

setInterval(refreshLiveConfigs, CONFIG_RELOAD_MS);

process.once("SIGINT", () => {
  for (const bot of botsBySlug.values()) bot.stop("SIGINT");
});
process.once("SIGTERM", () => {
  for (const bot of botsBySlug.values()) bot.stop("SIGTERM");
});
