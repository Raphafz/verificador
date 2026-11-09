import crypto from "crypto";

/** Headers HMAC alinhados a core/bridge_security.py */
export function bridgeAuthHeaders() {
  const token = process.env.ALERT_BRIDGE_API_TOKEN || "";
  const secret = (process.env.BRIDGE_HMAC_SECRET || "").trim();
  if (!token || !secret) {
    throw new Error("Defina ALERT_BRIDGE_API_TOKEN e BRIDGE_HMAC_SECRET");
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
