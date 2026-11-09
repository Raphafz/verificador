import { config } from "./config.js";
import { isWhatsAppReady, isWarmupComplete, sendText } from "./whatsapp.js";

const queue = [];
let processing = false;

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function randomDelayMs() {
  const min = config.antibanDelayMinMs;
  const max = config.antibanDelayMaxMs;
  if (max <= min) return min;
  return min + Math.floor(Math.random() * (max - min + 1));
}

function canSendNow() {
  if (!config.antibanEnabled) return { ok: true };

  if (!isWhatsAppReady()) {
    return { ok: false, reason: "WhatsApp offline" };
  }

  if (!isWarmupComplete()) {
    return {
      ok: false,
      reason: `aquecimento (${config.antibanWarmupSec}s após conectar)`,
    };
  }

  return { ok: true };
}

async function processQueue() {
  if (processing) return;
  processing = true;

  while (queue.length > 0) {
    const job = queue[0];
    const check = canSendNow();

    if (!check.ok) {
      console.log(`[antiban] Aguardando: ${check.reason}`);
      await sleep(3000);
      continue;
    }

    queue.shift();

    if (config.antibanDelayMaxMs > 0) {
      await sleep(randomDelayMs());
    }

    try {
      for (let i = 0; i < job.jids.length; i++) {
        await sendText(job.jids[i], job.text);
        if (config.antibanEnabled && i < job.jids.length - 1) {
          await sleep(config.antibanDelayBetweenTargetsMs);
        }
      }
      job.resolve();
    } catch (err) {
      job.reject(err);
    }
  }

  processing = false;
}

/** Fila com delay curto aleatório (alertas rápidos). */
export function scheduleWhatsAppSend(jids, text) {
  if (!config.antibanEnabled) {
    return (async () => {
      for (const jid of jids) await sendText(jid, text);
    })();
  }

  const check = canSendNow();
  if (!check.ok) {
    console.log(`[antiban] Aguardando envio: ${check.reason}`);
    return new Promise((resolve, reject) => {
      queue.push({ jids, text, resolve, reject });
      processQueue();
    });
  }

  return new Promise((resolve, reject) => {
    queue.push({ jids, text, resolve, reject });
    processQueue();
  });
}
