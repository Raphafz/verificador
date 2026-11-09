import { config } from "./config.js";

/**
 * Encaminha só alertas de largura de banda dos links configurados.
 * Ex.: Interface 100GE0/1/48(LINK.K2): Alto uso de largura de banda (>4.5%)
 */
export function shouldForwardAlert(text) {
  if (!config.alertFilterEnabled) return true;

  const normalized = text.replace(/\r\n/g, "\n");

  if (!normalized.includes(config.alertEventKeyword)) {
    return false;
  }

  return config.alertLinks.some((link) =>
    normalized.includes(`(${link})`)
  );
}
