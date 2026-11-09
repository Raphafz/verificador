# READINESS — Billing Asaas (Auditoria)

> **Modo:** READ ONLY  
> **Data:** 25/05/2026

---

## 1. Resumo executivo

Billing implementado como **webhook-driven** com modelo `CompanyBilling`. Integração **inbound only** — sem cliente API Asaas outbound evidente no código mapeado.

| Aspecto | Status |
|---------|--------|
| Webhook auth | ✅ Header token + timing-safe compare |
| CSRF | Exempt (esperado) |
| Idempotência | ❌ **AUSENTE** |
| Suspensão inadimplência | ⚠️ **PARCIAL** |
| Replay attack | ⚠️ Mitigado só por HTTPS + token |
| Tenant state consistency | ⚠️ Gaps identificados |

---

## 2. Modelo de dados

**Arquivo:** `core/models.py` — `CompanyBilling`

| Campo | Uso |
|-------|-----|
| `provider` | `manual` \| `asaas` |
| `asaas_customer_id` | Lookup webhook |
| `asaas_subscription_id` | Lookup webhook |
| `status` | trial / active / past_due / suspended / cancelled |
| `last_webhook_at` | Auditoria |
| `last_webhook_event` | Debug |

**Relação:** `OneToOne` → `Company` — `company.is_active` alterado por alguns eventos.

---

## 3. Webhook flow

**Arquivo:** `core/billing/asaas_webhook.py`  
**URL:** `POST /api/webhooks/asaas/` (`saas_viabilidade/urls.py`)

```
Request POST
  → ASAAS_WEBHOOK_TOKEN configurado? (503 se não)
  → token header válido? (403 se não)
  → rejeita ?token= query (log warning)
  → parse JSON
  → _find_billing(customer_id | subscription_id)
  → se não achar billing → 200 ok (silencioso)
  → atualiza last_webhook_*
  → switch event → apply_*()
```

---

## 4. Mapeamento eventos

| Evento Asaas | Método | Efeito billing | Efeito Company |
|--------------|--------|----------------|----------------|
| `PAYMENT_RECEIVED` | `apply_payment_received` | `active` + timestamp | `is_active=True` |
| `PAYMENT_CONFIRMED` | idem | idem | idem |
| `PAYMENT_RECEIVED_IN_CASH` | idem | idem | idem |
| `PAYMENT_OVERDUE` | `apply_payment_overdue` | `past_due` | **sem alteração** |
| `PAYMENT_DELETED` | idem | idem | **sem alteração** |
| `SUBSCRIPTION_DELETED` | `apply_subscription_cancelled` | `cancelled` | `is_active=False` |
| `SUBSCRIPTION_INACTIVATED` | idem | idem | idem |
| Outros | log debug | nenhum | nenhum |

---

## 5. Idempotência — CHECK

**Busca:** nenhum `payment.id`, `event.id` ou dedup table.

**Comportamento replay:**
- `apply_payment_received()` chamado N vezes → idempotente **funcionalmente** (sempre active)
- `apply_subscription_cancelled()` N vezes → idempotente (cancelled)
- **Risco:** eventos conflitantes sequenciais (received → overdue → received) dependem ordem Asaas

**Classificação idempotência:** ⚠️ **FRACA** — sem dedup por event ID.

---

## 6. Replay attack

| Controle | Presente |
|----------|----------|
| HTTPS | Depende deploy |
| Token secreto header | ✅ |
| Timestamp/nonce webhook | ❌ |
| IP allowlist Asaas | ❌ |
| Assinatura HMAC body | ❌ |

**Classificação:** ⚠️ **MÉDIO** — token vazado (Git histórico `.env`) permite replay até rotação.

---

## 7. Ativação / suspensão tenant

### Ativação ✅
Pagamento confirmado → `company.is_active = True`

### Inadimplência ⚠️
`PAYMENT_OVERDUE` → apenas `billing.status = past_due`  
**Company permanece ativa** — cliente continua usando produto.

### Cancelamento ✅
Subscription deleted → `company.is_active = False`

### Gap operacional
Status `suspended` existe no model **mas não é setado** pelo webhook mapeado.

---

## 8. Provider manual

RM pode gerenciar billing manualmente (`provider=manual`) — fluxo fora Asaas, sem webhook.

---

## 9. Tokens webhook

| Variável | Storage |
|----------|---------|
| `ASAAS_WEBHOOK_TOKEN` | `.env` only |
| `ASAAS_API_KEY` | `.env` — **sem uso outbound mapeado** |

**Git leak:** ASAAS keys **CONFIRMADAS** no histórico `.env` — ver `READINESS_GIT_SECRETS.md`.

---

## 10. Testes

**Arquivo:** `core/tests_security_api.py` — testes webhook token (referenciado docs).

---

## 11. Consistência tenant state

| Cenário | Consistente? |
|---------|--------------|
| Pagamento OK | ✅ |
| Inadimplência | ❌ Company ativa, billing past_due |
| Cancelamento | ✅ |
| Webhook sem billing local | ✅ 200 silencioso (pode mascarar misconfig) |
| DEBUG response | Expõe `event` + `company.slug` — só DEBUG |

---

## 12. Recomendações (NÃO executadas)

1. Dedup por `payment.id` + `event` em tabela `BillingWebhookEvent`
2. `PAYMENT_OVERDUE` → suspender após grace period (`company.is_active=False`)
3. Rotacionar `ASAAS_WEBHOOK_TOKEN` pós Git leak
4. Implementar cliente API Asaas para sync outbound (futuro comercial)
5. Alerta RM quando webhook sem billing match

---

## 13. Classificação

| Item | Status |
|------|--------|
| Webhook auth | ✅ OK |
| Idempotência | ❌ BLOCKER escala financeira |
| Suspensão inadimplência | ⚠️ BLOCKER comercial |
| Replay | ⚠️ ALTO se token vazado |
| Tenant consistency | ⚠️ MÉDIO |

**Score billing:** **55/100**

---

*Webhook não foi invocado — análise estática only.*
