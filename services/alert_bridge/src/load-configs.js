import "dotenv/config";
import { bridgeAuthHeaders } from "./bridge-auth.js";

export async function loadBridgeConfigs() {
  const url = process.env.ALERT_BRIDGE_API_URL;
  if (!url) {
    throw new Error("Defina ALERT_BRIDGE_API_URL no .env");
  }
  const res = await fetch(url, {
    headers: bridgeAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  const data = await res.json();
  return data.configs || [];
}
