/**
 * Sessões WhatsApp: uma pasta por empresa + linha (company_slug/line_id).
 */
import makeWASocket, {
  Browsers,
  DisconnectReason,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys";
import pino from "pino";
import path from "path";
import { fileURLToPath } from "url";
import qrcode from "qrcode-terminal";
import QRCode from "qrcode";
import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  renameSync,
  rmSync,
  writeFileSync,
} from "fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_ROOT = path.join(__dirname, "..", "data", "whatsapp");

const sessions = new Map();

function parseSessionKey(sessionKey) {
  const parts = String(sessionKey).split("/").filter(Boolean);
  return {
    company_slug: parts[0] || "default",
    line_id: parts[1] || "0",
    session_key: sessionKey,
  };
}

function pathsFor(sessionKey) {
  const safeParts = String(sessionKey)
    .split("/")
    .filter(Boolean)
    .map((p) => p.replace(/[^a-zA-Z0-9_-]/g, "_"));
  const dir = path.join(DATA_ROOT, ...safeParts);
  mkdirSync(dir, { recursive: true });
  return {
    dir,
    auth: path.join(dir, "auth_info"),
    qrPng: path.join(dir, "whatsapp-qr.png"),
    pairingFile: path.join(dir, "whatsapp-pairing-code.txt"),
    statusFile: path.join(dir, "status.json"),
  };
}

function defaultStatus(sessionKey, loginMode = "qr", label = "") {
  const meta = parseSessionKey(sessionKey);
  return {
    session_key: sessionKey,
    company_slug: meta.company_slug,
    line_id: meta.line_id,
    label,
    status: "disconnected",
    login_mode: loginMode,
    pairing_code: null,
    pairing_phone: null,
    message: "Desconectado",
    updated_at: new Date().toISOString(),
  };
}

function writeStatus(sessionKey, patch, label = "") {
  const current = sessions.get(sessionKey)?.status || defaultStatus(sessionKey, "qr", label);
  const next = { ...current, ...patch, updated_at: new Date().toISOString() };
  if (sessions.has(sessionKey)) {
    sessions.get(sessionKey).status = next;
  }
  writeFileSync(pathsFor(sessionKey).statusFile, JSON.stringify(next, null, 2), "utf8");
  return next;
}

export function hasSavedAuth(sessionKey) {
  const p = pathsFor(sessionKey).auth;
  if (!existsSync(p)) return false;
  try {
    return readdirSync(p).length > 0;
  } catch {
    return false;
  }
}

export function getSessionStatus(sessionKey) {
  let st = null;
  const inMemory = sessions.has(sessionKey);
  if (inMemory) {
    st = sessions.get(sessionKey).status;
  } else {
    const p = pathsFor(sessionKey);
    if (existsSync(p.statusFile)) {
      try {
        st = JSON.parse(readFileSync(p.statusFile, "utf8"));
      } catch {
        /* ignore */
      }
    }
  }
  if (!st) return defaultStatus(sessionKey);
  if (st.status === "qr" && !getQrImagePath(sessionKey)) {
    if (inMemory) {
      return { ...st, message: "Gerando QR Code…" };
    }
    return {
      ...st,
      status: "connecting",
      message: "Gerando QR Code…",
    };
  }
  return st;
}

async function saveQrPng(sessionKey, qrData, label) {
  const p = pathsFor(sessionKey);
  const tmp = `${p.qrPng}.tmp`;
  await QRCode.toFile(tmp, qrData, { width: 280, margin: 1 });
  if (existsSync(p.qrPng)) rmSync(p.qrPng, { force: true });
  renameSync(tmp, p.qrPng);
  const qrUpdatedAt = Date.now();
  writeStatus(
    sessionKey,
    {
      status: "qr",
      message: "Escaneie o QR Code",
      qr_updated_at: qrUpdatedAt,
    },
    label
  );
  return qrUpdatedAt;
}

export function isSessionReady(sessionKey) {
  const s = sessions.get(sessionKey);
  return Boolean(s?.ready && s?.sock);
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function closeSessionSocket(entry) {
  entry.ready = false;
  entry.pairingFlowRunning = false;
  if (!entry.sock) return;
  const old = entry.sock;
  entry.sock = null;
  try {
    old.ev.removeAllListeners("connection.update");
    old.ev.removeAllListeners("creds.update");
    await old.end(undefined);
  } catch {
    try {
      old.ws?.close();
    } catch {
      /* ignore */
    }
  }
}

async function runPairingFlow(entry, socket, phone, sessionKey, label) {
  if (entry.pairingFlowRunning) return;
  entry.pairingFlowRunning = true;
  const p = pathsFor(sessionKey);
  try {
    writeStatus(sessionKey, { status: "pairing", message: "Gerando código…", pairing_phone: phone }, label);
    await socket.waitForConnectionUpdate(
      (u) => Promise.resolve(u.connection === "connecting" || !!u.qr),
      90000
    );
    await sleep(2000);
    const code = await socket.requestPairingCode(phone);
    const formatted = code.length === 8 ? `${code.slice(0, 4)}-${code.slice(4)}` : code;
    writeFileSync(
      p.pairingFile,
      `${formatted}\n\nWhatsApp → Aparelhos conectados → Vincular com número → ${phone}`,
      "utf8"
    );
    writeStatus(
      sessionKey,
      { status: "pairing", pairing_code: formatted, message: "Digite o código no celular" },
      label
    );
    console.log(`[${sessionKey}] Pareamento: ${formatted}`);
  } catch (err) {
    writeStatus(sessionKey, { status: "error", message: err.message }, label);
  } finally {
    entry.pairingFlowRunning = false;
  }
}

async function startSession(sessionKey, options = {}) {
  const loginMode = options.loginMode === "pairing" ? "pairing" : "qr";
  const pairingPhone = (options.pairingPhone || "").replace(/\D/g, "");
  const label = options.label || "";
  const p = pathsFor(sessionKey);

  let entry = sessions.get(sessionKey);
  if (!entry) {
    entry = {
      sessionKey,
      sock: null,
      ready: false,
      isStarting: false,
      pairingFlowRunning: false,
      reconnectAttempts: 0,
      reconnectTimer: null,
      loginMode,
      pairingPhone,
      status: defaultStatus(sessionKey, loginMode, label),
    };
    sessions.set(sessionKey, entry);
  } else {
    entry.loginMode = loginMode;
    entry.pairingPhone = pairingPhone;
  }

  if (entry.isStarting) return entry;
  entry.isStarting = true;

  try {
    await closeSessionSocket(entry);
    writeStatus(
      sessionKey,
      {
        status: "connecting",
        login_mode: loginMode,
        pairing_phone: pairingPhone || null,
        pairing_code: null,
        message: loginMode === "qr" ? "Aguardando QR Code" : "Aguardando pareamento",
      },
      label
    );

    mkdirSync(p.auth, { recursive: true });
    const { state, saveCreds } = await useMultiFileAuthState(p.auth);

    entry.sock = makeWASocket({
      auth: state,
      printQRInTerminal: false,
      logger: pino({ level: "silent" }),
      browser: Browsers.windows("Chrome"),
      markOnlineOnConnect: false,
      syncFullHistory: false,
      generateHighQualityLinkPreview: false,
      connectTimeoutMs: 60000,
      defaultQueryTimeoutMs: 60000,
    });

    entry.sock.ev.on("creds.update", saveCreds);

    if (loginMode === "pairing" && !state.creds.registered) {
      if (!pairingPhone) {
        writeStatus(sessionKey, { status: "error", message: "Número obrigatório (pareamento)" }, label);
        throw new Error("pairing phone required");
      }
      void runPairingFlow(entry, entry.sock, pairingPhone, sessionKey, label);
    }

    entry.sock.ev.on("connection.update", (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr && loginMode === "qr") {
        qrcode.generate(qr, { small: true });
        const entryRef = entry;
        const now = Date.now();
        if (
          entryRef.qrSavedAt &&
          now - entryRef.qrSavedAt < 8000
        ) {
          return;
        }
        if (entryRef.qrWriting) {
          entryRef.qrPending = qr;
          return;
        }
        entryRef.qrWriting = true;
        void (async () => {
          try {
            await saveQrPng(sessionKey, qr, label);
            entryRef.qrSavedAt = Date.now();
          } catch (err) {
            writeStatus(
              sessionKey,
              { status: "error", message: `Falha ao gerar QR: ${err.message}` },
              label
            );
          } finally {
            entryRef.qrWriting = false;
            if (entryRef.qrPending) {
              const pending = entryRef.qrPending;
              entryRef.qrPending = null;
              if (Date.now() - (entryRef.qrSavedAt || 0) >= 8000) {
                entryRef.qrWriting = true;
                try {
                  await saveQrPng(sessionKey, pending, label);
                  entryRef.qrSavedAt = Date.now();
                } catch {
                  /* ignore */
                } finally {
                  entryRef.qrWriting = false;
                }
              }
            }
          }
        })();
      }

      if (connection === "open") {
        entry.ready = true;
        entry.reconnectAttempts = 0;
        writeStatus(sessionKey, { status: "connected", pairing_code: null, message: "Conectado" }, label);
        console.log(`[${sessionKey}] WhatsApp conectado (${label || "linha"}).`);
      }

      if (connection === "close") {
        entry.ready = false;
        const statusCode = lastDisconnect?.error?.output?.statusCode;
        if (
          statusCode === DisconnectReason.loggedOut ||
          statusCode === DisconnectReason.badSession
        ) {
          writeStatus(sessionKey, { status: "disconnected", message: "Sessão encerrada" }, label);
          return;
        }
        entry.reconnectAttempts += 1;
        if (entry.reconnectAttempts < 8) {
          setTimeout(() => startSession(sessionKey, options), 5000 * entry.reconnectAttempts);
        }
      }
    });
  } catch (err) {
    writeStatus(sessionKey, { status: "error", message: err.message }, label);
  } finally {
    entry.isStarting = false;
  }

  return entry;
}

export function lineSessionKey(companySlug, lineId) {
  return `${companySlug}/${lineId}`;
}

export async function ensureSessionForLine(line, companySlug) {
  const sessionKey = lineSessionKey(companySlug, line.line_id);
  const options = {
    loginMode: line.login_mode || "qr",
    pairingPhone: line.pairing_phone || "",
    label: line.label || "",
  };
  const entry = sessions.get(sessionKey);
  if (entry?.ready) return entry;
  if (entry?.isStarting) return entry;
  return startSession(sessionKey, options);
}

export async function reconnectSession(sessionKey, options = {}) {
  if (options.fresh !== false) {
    const st = getSessionStatus(sessionKey);
    const needsFresh =
      options.fresh === true ||
      !st ||
      st.status === "disconnected" ||
      st.status === "error";
    if (needsFresh) {
      disconnectSession(sessionKey, true);
    }
  }
  return startSession(sessionKey, options);
}

export function disconnectSession(sessionKey, deleteAuth = false) {
  const entry = sessions.get(sessionKey);
  if (entry) {
    if (entry.reconnectTimer) clearTimeout(entry.reconnectTimer);
    void closeSessionSocket(entry);
    sessions.delete(sessionKey);
  }
  const p = pathsFor(sessionKey);
  if (deleteAuth && existsSync(p.auth)) {
    rmSync(p.auth, { recursive: true, force: true });
  }
  if (existsSync(p.qrPng)) rmSync(p.qrPng, { force: true });
  if (existsSync(p.pairingFile)) rmSync(p.pairingFile, { force: true });
  writeStatus(sessionKey, { status: "disconnected", pairing_code: null, message: "Desconectado" });
}

export async function sendTextForSession(sessionKey, jid, text) {
  const entry = sessions.get(sessionKey);
  if (!entry?.sock || !entry.ready) {
    throw new Error(`WhatsApp não conectado (${sessionKey}).`);
  }
  await entry.sock.sendMessage(jid, { text });
}

export function getQrImagePath(sessionKey) {
  const p = pathsFor(sessionKey);
  return existsSync(p.qrPng) ? p.qrPng : null;
}

export function getPairingText(sessionKey) {
  const p = pathsFor(sessionKey);
  if (!existsSync(p.pairingFile)) return null;
  return readFileSync(p.pairingFile, "utf8");
}

/** Linhas que enviam alertas (multi-chip). */
export function resolveSenderSessionKeys(cfg) {
  const lines = cfg.whatsapp_lines || [];
  if (!lines.length) return [];

  const sendingIds = new Set((cfg.sending_line_ids || []).map(String));
  let picked = lines.filter((l) => sendingIds.has(String(l.line_id)));
  if (!picked.length) {
    picked = lines.filter((l) => l.send_alerts);
  }
  if (!picked.length) {
    const defId = cfg.default_whatsapp_line_id;
    const preferred = lines.find((l) => String(l.line_id) === String(defId));
    picked = [preferred || lines.find((l) => l.is_default) || lines[0]].filter(Boolean);
  }

  return picked.map((l) => lineSessionKey(cfg.company_slug, l.line_id));
}

/** Uma linha (compat). */
export function resolveSenderSessionKey(cfg) {
  const keys = resolveSenderSessionKeys(cfg);
  return keys[0] || null;
}
