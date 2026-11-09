# READINESS — Workers e Processos (Auditoria)

> **Modo:** READ ONLY  
> **Data:** 25/05/2026

---

## 1. Resumo executivo

| Worker | Integrado prod? | Monitoramento | Retry | Lock distribuído |
|--------|-----------------|---------------|-------|------------------|
| Alert Bridge (Node) | Manual | `check_bridge_health` | Poll 15s | Nonce HMAC (cache) |
| WhatsApp (Baileys) | Dentro Node | HTTP API + logs | Fila antiban | Por sessão disco |
| OLT worker | Docker/host | `olt_operations.log` | Re-enfileira | `olt:queue:processor` |
| Gunicorn | systemd | `/health/*` | Nginx restart | N/A |
| Cron LGPD | shell scripts | ❌ Manual | N/A | N/A |

**Veredicto:** workers críticos **existem** mas **não há orquestração unificada** — alto risco operacional silencioso.

---

## 2. Alert Bridge (MENSAGENS)

### Arquivos
- `MENSAGENS/src/index-saas.js` — entrypoint produção
- `core/alert_bridge_runner.py` — sobe com `runserver` em DEBUG
- `alerts/views.py` — `worker_configs_api`
- `core/bridge_security.py` — auth HMAC
- `saas_viabilidade/management/commands/check_bridge_health.py`

### Comportamento
| Aspecto | Detalhe |
|---------|---------|
| Start prod | Processo Node separado — **não** no `gunicorn.service` |
| Start dev | Auto se `RUN_ALERT_BRIDGE=true` + DEBUG |
| Config refresh | Poll 15s (`CONFIG_RELOAD_MS`) |
| Auth Django | IP + token + HMAC + nonce |
| Falha | `AlertBridgeConfig.last_error`; logs Node |
| Stale detection | `BRIDGE_STALE_MINUTES` + Sentry |

### Evidência runtime (logs locais 25/05)
```
GET /api/internal/alert-bridge/configs/ HTTP/1.1" 200
bridge_configs_fetch (audit log)
```
✅ Bridge **funcionando** em dev quando Django + Node up.

### Retry
- **Configs:** loop até API responder (boot)
- **Mensagens Telegram→WA:** ❌ sem retry automático de mensagem individual

### Race conditions
- Nonce cache previne replay HMAC
- Sem lock entre múltiplos workers Node (não previsto)

---

## 3. WhatsApp Bridge (Baileys)

### Arquivos
- `MENSAGENS/src/whatsapp-saas.js`
- `MENSAGENS/src/whatsapp-api.js` — HTTP :3921
- `alerts/whatsapp_client.py` — Django chama worker

### Storage sessão
```
MENSAGENS/data/whatsapp/{company_slug}/{line_id}/auth_info
```
**Risco:** redeploy sem backup → **re-QR obrigatório**.

### Retry / fila
- `antiban-saas.js` — delay entre envios
- Timeout 120s se WA não conecta → rejeita (não retry infinito)

### Monitoramento
- `WHATSAPP_BRIDGE_URL` health via Django views
- Fallback `status.json` local

---

## 4. OLT Worker

### Modos (`OLT_EXECUTION_MODE`)
| Modo | Execução |
|------|----------|
| `host` | Thread + `vpn_slot` mutex |
| `container` | `docker run` → `manage.py olt_run_job` |

### Arquivos
- `olt_ops/dispatcher.py`, `job_workers.py`, `queue.py`
- `olt_ops/vpn_manager.py`, `vpn_slot.py`
- `services/olt_worker/Dockerfile`

### Fila
```python
QUEUE_LOCK_KEY = "olt:queue:processor"  # cache.add TTL 30s
```
**Sem Redis:** lock locmem — **não funciona** entre workers Gunicorn.

### Retry
- `OltSlotBusyError` → re-enfileira
- VPN: poll TCP 2s até `OLT_VPN_CONNECT_TIMEOUT` (90s default)
- Mutex VPN host: wait até 600s

### Logs
- `logs/olt_operations.log` (sanitized)
- `OnuCleanupJob.log_output` no DB

---

## 5. Cron jobs (shell — não django-crontab)

| Script | Função | Monitoramento |
|--------|--------|---------------|
| `scripts/cron-lgpd-delete.sh` | DSR + activation tokens | ❌ Manual |
| `scripts/cron-lgpd-retention.sh` | Retenção LGPD | ❌ Manual |
| `scripts/cron-purge-caches.sh` | Geocoding cache | ❌ Manual |
| `backup-db.sh` | Backup PG | ❌ Manual |

**Gap:** nenhum script verifica exit code e alerta — depende de operador configurar cron + mail.

---

## 6. Redis

| Uso | Sem Redis |
|-----|-----------|
| Rate limit global | Degrada locmem |
| Bridge nonce anti-replay | **Falha entre workers** |
| OLT queue lock | **Falha entre workers** |
| Login lockout | Degrada |
| MFA remember device | Degrada |

**Classificação:** Redis **recomendado obrigatório** se Gunicorn workers > 1.

---

## 7. Sentry

- `saas_viabilidade/sentry_bootstrap.py`
- Bridge stale → alerta via `check_bridge_health`
- `/sentry-debug/` só DEBUG

---

## 8. systemd (deploy)

**Arquivo:** `gunicorn.service` — só Django.

**Não inclui:**
- Alert Bridge Node
- OLT Docker daemon policy
- Cron wrappers

---

## 9. Stale workers — cenários

| Cenário | Sintoma | Detecção |
|---------|---------|----------|
| Node crash | Alertas param | `check_bridge_health`, last poll > stale |
| WA desconectado | PV não recebe | UI QR, logs Node |
| OLT job stuck queued | UI "na fila" forever | Manual check job status |
| Gunicorn worker hang | 502 Nginx | `/health/ready` |

---

## 10. Recomendações (NÃO executadas)

1. systemd units para `MENSAGENS` (prod)
2. Cron + alerta se `check_bridge_health` exit != 0
3. Redis em prod multi-worker
4. Runbook backup sessão WhatsApp antes deploy
5. Dashboard operacional: bridge heartbeat + OLT queue depth

---

## 11. Classificação

| Item | Status |
|------|--------|
| Bridge funcional (dev) | ✅ Evidência logs |
| Bridge prod orchestration | ❌ Manual |
| OLT queue reliability | ⚠️ Depende Redis |
| Cron monitorado | ❌ |
| Retry mensagens alerta | ❌ |

**Score workers:** **52/100**

---

*Inspeção read-only — processos não foram reiniciados.*
