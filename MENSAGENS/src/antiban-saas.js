import { isSessionReady, sendTextForSession } from "./whatsapp-saas.js";

const queues = new Map();

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function randomDelayMs(cfg) {
  const min = cfg.antiban_delay_min_ms ?? 1000;
  const max = cfg.antiban_delay_max_ms ?? 6000;
  if (max <= min) return min;
  return min + Math.floor(Math.random() * (max - min + 1));
}

function getQueue(sessionKey) {
  if (!queues.has(sessionKey)) {
    queues.set(sessionKey, { items: [], processing: false });
  }
  return queues.get(sessionKey);
}

async function processQueue(sessionKey, cfg) {
  const q = getQueue(sessionKey);
  if (q.processing) return;
  q.processing = true;

  while (q.items.length > 0) {
    const job = q.items[0];
    if (!isSessionReady(sessionKey)) {
      const waited = Date.now() - (job.queuedAt || Date.now());
      if (waited > 120000) {
        q.items.shift();
        job.reject(new Error("WhatsApp não conectado no worker (timeout 2 min)."));
        continue;
      }
      await sleep(3000);
      continue;
    }
    q.items.shift();
    if (cfg.antiban_enabled !== false && cfg.antiban_delay_max_ms > 0) {
      await sleep(randomDelayMs(cfg));
    }
    try {
      for (let i = 0; i < job.jids.length; i++) {
        await sendTextForSession(sessionKey, job.jids[i], job.text);
        if (cfg.antiban_enabled !== false && i < job.jids.length - 1) {
          await sleep(2000);
        }
      }
      job.resolve();
    } catch (err) {
      job.reject(err);
    }
  }

  q.processing = false;
}

export function scheduleWhatsAppSend(sessionKey, jids, text, cfg) {
  if (!sessionKey) {
    return Promise.reject(new Error("Nenhuma linha WhatsApp configurada para envio."));
  }

  if (!cfg.antiban_enabled) {
    return (async () => {
      for (const jid of jids) {
        await sendTextForSession(sessionKey, jid, text);
      }
    })();
  }

  return new Promise((resolve, reject) => {
    getQueue(sessionKey).items.push({ jids, text, resolve, reject, queuedAt: Date.now() });
    processQueue(sessionKey, cfg);
  });
}
