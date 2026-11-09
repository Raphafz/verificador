import makeWASocket, {
  Browsers,
  DisconnectReason,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys";
import { config } from "./config.js";
import pino from "pino";
import path from "path";
import { fileURLToPath } from "url";
import qrcode from "qrcode-terminal";
import QRCode from "qrcode";
import { writeFileSync } from "fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUTH_DIR = path.join(__dirname, "..", "auth_info");
const QR_PNG = path.join(__dirname, "..", "whatsapp-qr.png");
const PAIRING_CODE_FILE = path.join(__dirname, "..", "whatsapp-pairing-code.txt");

const RECONNECT_BASE_MS = 5000;
const MAX_RECONNECT_ATTEMPTS = 8;

let sock = null;
let ready = false;
let isStarting = false;
let reconnectTimer = null;
let reconnectAttempts = 0;
let connectResolve = null;
let connectedAt = 0;

function getStatusCode(lastDisconnect) {
  return lastDisconnect?.error?.output?.statusCode;
}

function shouldReconnect(statusCode) {
  if (statusCode == null) return true;
  if (statusCode === DisconnectReason.loggedOut) return false;
  if (statusCode === DisconnectReason.badSession) return false;
  if (statusCode === DisconnectReason.forbidden) return false;
  if (statusCode === DisconnectReason.multideviceMismatch) return false;
  if (statusCode === DisconnectReason.connectionReplaced) return false;
  return true;
}

async function closeSocket() {
  ready = false;
  pairingFlowRunning = false;
  if (!sock) return;

  const old = sock;
  sock = null;

  try {
    old.ev.removeAllListeners("connection.update");
    old.ev.removeAllListeners("creds.update");
    await old.end(undefined);
  } catch {
    try {
      old.ws?.close();
    } catch {
      /* ignorar */
    }
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function showPairingCode(code, phone) {
  const formatted =
    code.length === 8 ? `${code.slice(0, 4)}-${code.slice(4)}` : code;
  const instructions =
    `\n=== CÓDIGO DE PAREAMENTO WhatsApp ===\n\n` +
    `Código: ${formatted}\n\n` +
    `NÃO é SMS. O código aparece aqui no terminal (e em whatsapp-pairing-code.txt).\n\n` +
    `No celular (${phone}):\n` +
    `  WhatsApp → ⋮ → Aparelhos conectados → Conectar aparelho\n` +
    `  → Vincular com número de telefone → digite o código acima\n\n` +
    `Válido por poucos minutos. Aguarde "WhatsApp conectado."\n`;
  console.log(instructions);
  writeFileSync(PAIRING_CODE_FILE, `${formatted}\n${instructions}`, "utf8");
  console.log(`Código salvo em: ${PAIRING_CODE_FILE}\n`);
}

let pairingFlowRunning = false;

async function runPairingFlow(socket, phone) {
  if (pairingFlowRunning) return;
  pairingFlowRunning = true;

  try {
    console.log("Aguardando conexão com WhatsApp para gerar código...\n");
    await socket.waitForConnectionUpdate(
      (u) => Promise.resolve(u.connection === "connecting" || !!u.qr),
      90000
    );
    await sleep(2000);
    const code = await socket.requestPairingCode(phone);
    showPairingCode(code, phone);
  } catch (err) {
    console.error("Erro ao gerar código de pareamento:", err.message);
    console.error(
      "Tente apagar auth_info/, use WHATSAPP_LOGIN_MODE=qr ou rode npm start de novo.\n"
    );
  } finally {
    pairingFlowRunning = false;
  }
}

function scheduleReconnect(statusCode) {
  if (reconnectTimer) return;

  if (!shouldReconnect(statusCode)) {
    if (statusCode === DisconnectReason.connectionReplaced) {
      console.error(
        "\nOutra sessão WhatsApp está ativa (outro PC, outro npm start ou muitos 'Aparelhos conectados').\n" +
          "Feche sessões extras no celular: WhatsApp → Aparelhos conectados → desconecte as outras.\n" +
          "Depois apague auth_info/ se precisar e rode npm start de novo (só UMA vez).\n"
      );
    } else {
      console.error(
        "\nSessão inválida. Apague a pasta auth_info/ e escaneie o QR de novo.\n"
      );
    }
    return;
  }

  if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
    console.error(
      `\nMuitas reconexões seguidas (${MAX_RECONNECT_ATTEMPTS}). Pare o script (Ctrl+C), ` +
        `feche outras sessões WhatsApp Web, apague auth_info/ e tente novamente.\n`
    );
    return;
  }

  reconnectAttempts += 1;
  const delay = RECONNECT_BASE_MS * reconnectAttempts;

  console.log(
    `WhatsApp desconectou (código ${statusCode ?? "?"}). Nova tentativa em ${delay / 1000}s...`
  );

  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    startWhatsApp();
  }, delay);
}

async function startWhatsApp() {
  if (isStarting) return;
  isStarting = true;

  try {
    await closeSocket();

    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

    sock = makeWASocket({
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

    sock.ev.on("creds.update", saveCreds);

    if (config.whatsappLoginMode === "pairing" && !state.creds.registered) {
      const phone = config.whatsappPairingPhone;
      if (!phone) {
        throw new Error(
          "WHATSAPP_LOGIN_MODE=pairing exige WHATSAPP_PAIRING_PHONE no .env (DDI+DDD+número, só dígitos, ex: 5521999999999)"
        );
      }
      void runPairingFlow(sock, phone);
    }

    sock.ev.on("connection.update", (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr && config.whatsappLoginMode === "qr") {
        console.clear();
        console.log("\n=== QR CODE WhatsApp ===\n");
        qrcode.generate(qr, { small: true });

        QRCode.toFile(QR_PNG, qr)
          .then(() => {
            console.log(`QR em imagem (se não aparecer acima): ${QR_PNG}\n`);
          })
          .catch((err) => {
            console.error(
              "Não foi possível salvar whatsapp-qr.png:",
              err.message
            );
          });

        console.log("WhatsApp → Aparelhos conectados → Conectar aparelho\n");
      } else if (qr && config.whatsappLoginMode === "pairing") {
        console.log(
          "Modo pareamento: aguarde o código de 8 caracteres no terminal.\n"
        );
      }

      if (connection === "open") {
        ready = true;
        connectedAt = Date.now();
        reconnectAttempts = 0;
        console.log("WhatsApp conectado.");
        if (config.antibanEnabled) {
          console.log(
            `[antiban] Aquecimento ${config.antibanWarmupSec}s antes do primeiro envio.`
          );
        }
        connectResolve?.(sock);
        connectResolve = null;
      }

      if (connection === "close") {
        ready = false;
        const statusCode = getStatusCode(lastDisconnect);
        scheduleReconnect(statusCode);
      }
    });
  } finally {
    isStarting = false;
  }
}

export function isWhatsAppReady() {
  return ready;
}

export function isWarmupComplete() {
  if (!config.antibanEnabled) return true;
  if (!connectedAt) return false;
  return Date.now() - connectedAt >= config.antibanWarmupSec * 1000;
}

export async function connectWhatsApp() {
  if (ready && sock) return sock;

  return new Promise((resolve) => {
    if (!connectResolve) connectResolve = resolve;
    startWhatsApp();
  });
}

export async function sendText(jid, text) {
  if (!sock || !ready) {
    throw new Error("WhatsApp ainda não está conectado.");
  }
  await sock.sendMessage(jid, { text });
}

export async function sendTextToMany(jids, text) {
  for (const jid of jids) {
    await sendText(jid, text);
  }
}

export async function listGroups() {
  if (!sock || !ready) {
    throw new Error("WhatsApp ainda não está conectado.");
  }

  const groups = await sock.groupFetchAllParticipating();
  return Object.values(groups).map((g) => ({
    name: g.subject,
    jid: g.id,
  }));
}
