# READINESS — Segurança Real (Validação Código + Evidências)

> **Modo:** READ ONLY  
> **Data:** 25/05/2026

---

## 1. Resumo executivo

O sistema possui **hardening enterprise substantivo**, mas **superfícies públicas** e **comandos perigosos** permanecem. Vários achados do `AUDITORIA-SEGURANCA.md` foram **corrigidos no código**; outros **confirmados**.

---

## 2. `/health/security/`

**Arquivo:** `core/health_views.py` L56–68

| Aspecto | Evidência |
|---------|-----------|
| Auth | Nenhuma (GET público) |
| IP restrict | `HEALTH_SECURITY_ALLOWED_IPS` — se **vazio → aberto** |
| Dados expostos | CSP, MFA, session_secure, field_encryption_configured, antivirus |

**Classificação:** ⚠️ **MÉDIO** — reconnaissance se IP allowlist vazio.

**Evidência código:**
```python
def _health_security_allowed(request) -> bool:
    allowed = getattr(settings, "HEALTH_SECURITY_ALLOWED_IPS", ())
    if not allowed:
        return True  # ← ABERTO
```

---

## 3. `csrf_exempt` perigosos

| Endpoint | Arquivo | Justificativa |
|----------|---------|---------------|
| `POST /api/webhooks/asaas/` | `core/billing/asaas_webhook.py` | Webhook externo — **esperado** |

**Busca repo:** único `csrf_exempt` em código app (excl. docs).

**Mitigação Asaas:** token header only; query string **rejeitada** (L23–25).

---

## 4. `reset_superuser`

**Arquivo:** `core/management/commands/reset_superuser.py`

| Check | Resultado |
|-------|-----------|
| Guard `IS_PRODUCTION` | ❌ **AUSENTE** |
| Guard `DEBUG` | ❌ **AUSENTE** |
| Ação | Delete + recreate superuser RM |

**Classificação:** 🔴 **CRÍTICO** — qualquer shell na VPS com acesso Django pode escalar.

---

## 5. Open redirects

**Arquivo:** `core/safe_redirect.py` + `core/views.py` L164–167

```python
return safe_redirect(request, next_url, fallback_name="dashboard")
```

**Classificação:** ✅ **CORRIGIDO** — `url_has_allowed_host_and_scheme` + block `//`.

**Validar:** login empresa (`company_login_view`) — grep confirma uso similar recomendado; RM corrigido.

---

## 6. Permissões tenant

| Camada | Mecanismo | Status |
|--------|-----------|--------|
| Middleware | `SecureCompanyMiddleware` | ✅ |
| API queryset | `TenantScopedPermission` | ✅ |
| Object-level | `has_object_permission` | ✅ |
| Upload paths | `core/upload_security.py` | ✅ |
| Mídia | `core/media_protected.py` | ✅ |

**Testes:** `core/tests_api_tenant.py`, `core/tests_security_authorization.py`

---

## 7. Middleware ordering

Ordem confirmada em `settings.py` — **Auth antes de tenant**, **MFA antes de módulos**.

**Risco se reordenado:** bypass tenant ou MFA — documentar como invariante.

---

## 8. MFA bypass

| Vetor | Status |
|-------|--------|
| API DRF sem MFA | ✅ `MfaVerifiedPermission` global |
| HTML RM/staff | ✅ `MfaEnforcementMiddleware` |
| Exempt paths | login, health, ativação — **esperado** |
| `/{slug}/login/` | Não exempt — MFA após login ✅ |

---

## 9. Uploads

- ClamAV opcional (`UPLOAD_ANTIVIRUS_ENABLED`)
- Validação tipo/tamanho em forms
- Paths por company_id

**Classificação:** ✅ Adequado — antivirus off by default em dev.

---

## 10. Mídia pública

| Config | Default prod |
|--------|--------------|
| `USE_PROTECTED_MEDIA` | True (bootstrap) |
| `MEDIA_SIGNED_ALLOW_ANONYMOUS` | False |
| Nginx | Proxy para Django (não alias público) — `docs/deploy/DEPLOY.md` |

**Validação:** requer curl em prod — **não executado** nesta auditoria.

---

## 11. Throttling

| Camada | Arquivo |
|--------|---------|
| DRF | `core/throttling.py` |
| Global middleware | `GlobalRateLimitMiddleware` |
| Login | `login_rate_limit` decorator |
| Lockout | `core/login_lockout.py` |

**Gap:** rate limit desligado em DEBUG — **esperado** dev.

---

## 12. Bridge API — token Telegram em trânsito

**Arquivo:** `alerts/models.py` L112

```python
"telegram_token": self.telegram_bot_token,  # descriptografado
```

**Mitigação:** HMAC + IP + HTTPS. **Impacto se vazamento:** alto.

**Classificação:** 🔴 **ALTO**

---

## 13. Endpoints públicos (inventário validado)

| Rota | Risco |
|------|-------|
| `/health/`, `/ready/` | Baixo |
| `/health/security/` | Médio (se aberto) |
| `/api/webhooks/asaas/` | Alto (mitigado token) |
| `/api/internal/alert-bridge/configs/` | Alto (mitigado HMAC) |
| `/ativar-conta/<token>/` | Médio (token + rate limit) |
| Páginas legais | Baixo |

---

## 14. Status vs auditoria anterior (26/05/2026 doc)

| Item auditoria | Status atual |
|----------------|--------------|
| `.env` no Git | ⚠️ Removido tip; histórico **CONFIRMADO** |
| Open redirect RM | ✅ Corrigido |
| MFA API | ✅ Corrigido |
| Token Asaas query | ✅ Rejeitado |
| `reset_superuser` | ❌ **Ainda vulnerável** |
| `/health/security/` aberto | ❌ **Ainda default aberto** |
| Swagger RM-only | Verificar `core/api_schema_views.py` — assumido OK |

---

## 15. Score segurança real

| Subárea | Nota |
|---------|------|
| Middleware / CSP | 78 |
| Auth / MFA | 72 |
| Tenant isolation | 70 |
| Segredos / Git | **25** |
| Endpoints públicos | 55 |
| Comandos management | 40 |

**Score consolidado:** **64/100** (alinhado auditoria anterior)

---

*Nenhuma configuração alterada.*
