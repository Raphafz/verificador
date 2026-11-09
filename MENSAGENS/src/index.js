// Libsignal (Baileys) imprime "Closing session" no primeiro PV — não é erro.
const _info = console.info;
console.info = (...args) => {
  const first = args[0];
  if (typeof first === "string" && first.includes("Closing session")) return;
  if (first && typeof first === "object" && String(first).includes("SessionEntry")) return;
  _info.apply(console, args);
};

import { config } from "./config.js";
import { connectWhatsApp } from "./whatsapp.js";
import { startTelegramBot } from "./telegram.js";

console.log("=== Telegram → WhatsApp (somente texto) ===\n");

if (!config.telegramGroupId) {
  console.log(
    "Dica: deixe TELEGRAM_GROUP_ID vazio, mande uma msg no grupo Telegram e copie o ID que aparecer aqui.\n"
  );
}

if (config.whatsappAlertPhones.length === 0 && !config.whatsappGroupJid) {
  console.log(
    "Dica: use WHATSAPP_ALERT_PHONES no .env (PV) ou WHATSAPP_GROUP_JID (grupo).\n"
  );
} else if (config.whatsappAlertPhones.length > 0) {
  console.log(`Alertas no PV para: ${config.whatsappAlertPhones.join(", ")}\n`);
}

if (config.whatsappLoginMode === "pairing") {
  console.log(
    `Login WhatsApp: código de pareamento (número ${config.whatsappPairingPhone ?? "defina WHATSAPP_PAIRING_PHONE"})\n`
  );
} else {
  console.log("Login WhatsApp: QR Code (whatsapp-qr.png)\n");
}

await connectWhatsApp();
startTelegramBot();
