/**
 * API HTTP: /whatsapp/{company_slug}/{line_id}/...
 */
import http from "http";
import { readFileSync } from "fs";
import {
  disconnectSession,
  getPairingText,
  getQrImagePath,
  getSessionStatus,
  lineSessionKey,
  reconnectSession,
} from "./whatsapp-saas.js";

const PORT = parseInt(process.env.WHATSAPP_BRIDGE_PORT || "3921", 10);

function bridgeToken() {
  return process.env.ALERT_BRIDGE_API_TOKEN || "";
}

function authorized(req) {
  const token = bridgeToken();
  const h = req.headers["x-bridge-token"];
  return token && h === token;
}

function json(res, code, body) {
  res.writeHead(code, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(body));
}

function readBody(req) {
  return new Promise((resolve) => {
    let data = "";
    req.on("data", (c) => (data += c));
    req.on("end", () => {
      try {
        resolve(data ? JSON.parse(data) : {});
      } catch {
        resolve({});
      }
    });
  });
}

export function startWhatsappApiServer() {
  const server = http.createServer(async (req, res) => {
    if (!authorized(req)) {
      return json(res, 401, { error: "Unauthorized" });
    }

    const url = new URL(req.url || "/", `http://127.0.0.1:${PORT}`);
    const parts = url.pathname.split("/").filter(Boolean);

    if (parts[0] === "ping") {
      return json(res, 200, { ok: true });
    }

    if (parts[0] !== "whatsapp" || parts.length < 3) {
      return json(res, 404, { error: "Not found" });
    }

    const companySlug = decodeURIComponent(parts[1]);
    const lineId = decodeURIComponent(parts[2]);
    const sessionKey = lineSessionKey(companySlug, lineId);
    const action = parts[3] || "";

    if (!action && req.method === "GET") {
      return json(res, 200, getSessionStatus(sessionKey));
    }

    if (action === "connect" && req.method === "POST") {
      const body = await readBody(req);
      const mode = body.mode === "pairing" ? "pairing" : "qr";
      const phone = String(body.phone || "").replace(/\D/g, "");
      const label = body.label || "";
      const fresh = body.fresh !== false;
      void reconnectSession(sessionKey, {
        loginMode: mode,
        pairingPhone: phone,
        label,
        fresh,
      });
      return json(res, 200, { ok: true, session_key: sessionKey, fresh });
    }

    if (action === "disconnect" && req.method === "POST") {
      const body = await readBody(req);
      disconnectSession(sessionKey, Boolean(body.delete_auth));
      return json(res, 200, { ok: true });
    }

    if (action === "qr.png" && req.method === "GET") {
      const file = getQrImagePath(sessionKey);
      if (!file) {
        return json(res, 404, { error: "QR ainda não gerado" });
      }
      const buf = readFileSync(file);
      res.writeHead(200, { "Content-Type": "image/png", "Cache-Control": "no-store" });
      return res.end(buf);
    }

    if (action === "pairing-code" && req.method === "GET") {
      const text = getPairingText(sessionKey);
      if (!text) {
        return json(res, 404, { error: "Código indisponível" });
      }
      return json(res, 200, { code_text: text });
    }

    return json(res, 404, { error: "Not found" });
  });

  server.on("error", (err) => {
    if (err.code === "EADDRINUSE") {
      console.warn(
        `[whatsapp-api] Porta ${PORT} já em uso — este processo segue só com Telegram. ` +
          "Encerre o Node antigo ou use um único runserver."
      );
      return;
    }
    console.error("[whatsapp-api] Erro no servidor HTTP:", err);
    process.exit(1);
  });

  server.listen(PORT, "127.0.0.1", () => {
    console.log(`[whatsapp-api] http://127.0.0.1:${PORT}/whatsapp/{empresa}/{linha}/...`);
  });

  return server;
}
