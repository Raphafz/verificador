import "dotenv/config";
import crypto from "crypto";

function bridgeAuthHeaders() {
  const token = process.env.ALERT_BRIDGE_API_TOKEN || "";
  const secret = (process.env.BRIDGE_HMAC_SECRET || token).trim();
  if (!token || !secret) {
    return { "X-Bridge-Token": token };
  }
  const ts = String(Math.floor(Date.now() / 1000));
  const nonce = crypto.randomBytes(18).toString("base64url");
  const msg = `${ts}.${nonce}.${token}`;
  const sig = crypto.createHmac("sha256", secret).update(msg).digest("hex");
  return {
    "X-Bridge-Token": token,
    "X-Bridge-Timestamp": ts,
    "X-Bridge-Nonce": nonce,
    "X-Bridge-Signature": sig,
  };
}

export async function loadBridgeConfigsFromSaas() {
  const url = process.env.ALERT_BRIDGE_API_URL;
  const token = process.env.ALERT_BRIDGE_API_TOKEN;
  if (!url || !token) {
    return null;
  }
  const controller = new AbortController();
  const timeoutMs = Number(process.env.BRIDGE_FETCH_TIMEOUT_MS || "15000");
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      headers: bridgeAuthHeaders(),
      signal: controller.signal,
    });
    if (!res.ok) {
      throw new Error(`API SaaS ${res.status}: ${await res.text()}`);
    }
    const data = await res.json();
    return data.configs || [];
  } finally {
    clearTimeout(timer);
  }
}
