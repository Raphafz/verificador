import { Telegraf } from "telegraf";
import { config, getWhatsAppTargets } from "./config.js";
import { shouldForwardAlert } from "./filters.js";
import { isWhatsAppReady } from "./whatsapp.js";
import { scheduleWhatsAppSend } from "./antiban.js";

function senderName(from) {
  const parts = [from.first_name, from.last_name].filter(Boolean);
  const name = parts.join(" ").trim();
  return name || from.username || `id${from.id}`;
}

function formatMessage(from, text) {
  if (from?.is_bot) return text;
  return `${config.messagePrefix} ${senderName(from)}\n${text}`;
}

function matchedLink(text) {
  return config.alertLinks.find((link) => text.includes(`(${link})`));
}

export function startTelegramBot() {
  const bot = new Telegraf(config.telegramToken);

  if (config.alertFilterEnabled) {
    console.log(
      `Filtro ativo: links (${config.alertLinks.join(", ")}) + "${config.alertEventKeyword}"`
    );
  }
  if (config.antibanEnabled) {
    console.log(
      `[antiban] delay ${config.antibanDelayMinMs}-${config.antibanDelayMaxMs}ms, aquecimento ${config.antibanWarmupSec}s`
    );
  }

  bot.on("message", async (ctx) => {
    const chat = ctx.chat;
    const from = ctx.from;

    if (!chat || chat.type === "private") return;

    const text = ctx.message.text ?? ctx.message.caption ?? null;
    if (!text) return;

    if (!shouldForwardAlert(text)) return;

    if (from?.is_bot && !config.alertFilterEnabled) return;
    if (!from && !config.alertFilterEnabled) return;

    if (config.telegramGroupId && String(chat.id) !== config.telegramGroupId) {
      return;
    }

    if (!config.telegramGroupId) {
      console.log(
        `[Telegram] Grupo "${chat.title}" → TELEGRAM_GROUP_ID=${chat.id}`
      );
    }

    const targets = getWhatsAppTargets();
    if (targets.length === 0) {
      console.log(
        "Defina WHATSAPP_ALERT_PHONES ou WHATSAPP_GROUP_JID no .env"
      );
      return;
    }

    if (!isWhatsAppReady()) {
      console.log("WhatsApp offline; mensagem ignorada.");
      return;
    }

    try {
      const body = formatMessage(from, text);
      await scheduleWhatsAppSend(targets, body);
      const link = matchedLink(text);
      const label = link ? `link ${link}` : senderName(from);
      const dest =
        config.whatsappAlertPhones.length > 0 ? "PV" : "grupo";
      console.log(`Espelhado (${label}) → WhatsApp (${dest})`);
    } catch (err) {
      console.error("Erro ao enviar para WhatsApp:", err.message);
    }
  });

  bot.launch();
  console.log("Bot Telegram ativo (aguardando mensagens no grupo).");

  process.once("SIGINT", () => bot.stop("SIGINT"));
  process.once("SIGTERM", () => bot.stop("SIGTERM"));
}
