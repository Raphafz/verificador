# RELATÓRIO DJANGO LGPD + SEGURANÇA

**Projeto:** Saas-Verificador-de-Viabilidade (RM Systems)  
**Tipo:** Auditoria técnica completa (read-only)  
**Data:** 23 de maio de 2026  
**Escopo:** Repositório raiz — Django 5.x, DRF, PostgreSQL, multi-tenant B2B  
**Metodologia:** Mapeamento estrutural, grep automatizado, leitura de settings/middleware/models/views, CI, nginx, docs

**Documentos relacionados:** `docs/internal/MELHORIAS_A_FAZER.md`, `docs/deploy/ROTACAO_SECRETS.md`, `docs/commercial/WHATSAPP_CONTINGENCIA.md`

---

## RESUMO EXECUTIVO

| Métrica | Valor | Interpretação |
|---------|-------|---------------|
| **Risco geral** | **Médio–Alto** | Base de segurança acima da média; `.env` versionado com segredos reais eleva risco de vazamento |
| **Score segurança** | **74 / 100** | Hardening sólido em produção; gaps em segredos, API interna e isenções de middleware |
| **Score LGPD** | **78 / 100** | Portal do titular, consentimento, export/anonimização maduros; faltam retificação e trilha em exports admin |

### Pontos fortes

- Boot fail-safe (`saas_viabilidade/security_bootstrap.py`) bloqueia `DEBUG`, `SECRET_KEY` fraca e mídia pública em produção
- MFA (TOTP), lockout de login/MFA, rate limiting, CSP com nonce, Argon2 (mín. 14 caracteres)
- Criptografia em repouso: CNPJ, tokens Telegram, senhas OLT/VPN (`EncryptedCharField`)
- Mídia `/media/` via Nginx → Django autenticado (sem `alias` público) — `nginx.conf:40-49`
- LGPD: `ConsentRecord`, portal `/meus-dados/`, export ZIP assinado, anonimização, retenção automatizada
- API DRF com escopo tenant + testes anti-IDOR (`core/tests_api_tenant.py`)

### Achado crítico imediato

**`.env` está rastreado no Git** (`git ls-files .env` confirma presença) com `SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `OPENROUTESERVICE_API_KEY`, `ALERT_BRIDGE_API_TOKEN` e outros segredos. O comentário em `.gitignore:153` indica repo privado, mas isso **não elimina** risco de fork, leak, ex-funcionário ou repositório público acidental.

---

## 1. MAPEAMENTO DO PROJETO

### 1.1 Estrutura Django

| Componente | Caminho |
|------------|---------|
| `manage.py` | Raiz do repositório |
| Settings ativo | `saas_viabilidade/settings.py` |
| Settings legado | `saas_viabilidade/settings_production.py` (deprecado — `RuntimeError` no import) |
| WSGI / ASGI | `saas_viabilidade/wsgi.py`, `asgi.py` |
| Env loader | `saas_viabilidade/env_loader.py` |
| ROOT URLCONF | `saas_viabilidade/urls.py` |

### 1.2 Apps locais

| App | Função |
|-----|--------|
| `core` | Tenants, usuários, LGPD, tickets, API DRF, painel RM |
| `ftth_viewer` | Verificador FTTH, geocoding, viabilidade |
| `alerts` | Bridge Telegram → WhatsApp |
| `olt_ops` | OLT/ONU, VPN, jobs Docker |
| `saas_viabilidade` | Bootstrap, logging, Sentry |

### 1.3 URLs principais

| Arquivo | Papel |
|---------|-------|
| `core/api_urls.py` | API REST `/api/v1/` |
| `core/urls_rm.py` | Painel RM `/rm/` |
| `core/urls_company.py` | Rotas por tenant `/<slug>/` |
| `ftth_viewer/urls.py` | Verificador `/verificador/` |
| `alerts/urls.py` | Alertas por empresa |
| `olt_ops/urls.py` | OLT/ONU por empresa |

### 1.4 Infraestrutura detectada

| Componente | Status |
|------------|--------|
| PostgreSQL | Sim (`psycopg`, `DATABASE_URL`) |
| Redis | Opcional (`django-redis`, cache/rate-limit) |
| Gunicorn | Sim (`gunicorn_config.py`, `gunicorn.service`) |
| Nginx | Sim (`nginx.conf`) |
| Docker (app principal) | Não (sem compose na raiz) |
| Docker OLT worker | Sim (`services/olt_worker/Dockerfile`) |
| Celery | **Não** |
| SQLite | Apenas CI (`.github/workflows/tests.yml`) |

### 1.5 Frameworks e bibliotecas (`requirements.txt`)

| Presente | Ausente |
|----------|---------|
| Django, DRF, drf-spectacular | SimpleJWT / PyJWT |
| django-otp, pyotp, qrcode | django-cors-headers |
| argon2-cffi, cryptography | Celery, Channels |
| gunicorn, whitenoise, sentry-sdk | Stripe SDK (webhook Asaas manual) |
| pandas, paramiko, django-redis | Firebase, Supabase, S3, Cloudinary |

**Autenticação API:** sessão Django (`SessionAuthentication`) — **sem JWT**.

### 1.6 Middleware (ordem em `settings.py`)

1. `SecurityMiddleware`
2. `WhiteNoiseMiddleware`
3. `RequestIdMiddleware`
4. `CspNonceMiddleware`
5. `SessionMiddleware`
6. `CommonMiddleware`
7. `CsrfViewMiddleware`
8. `AuthenticationMiddleware`
9. `OTPMiddleware`
10. `MfaEnforcementMiddleware`
11. `SessionIdleTimeoutMiddleware`
12. `SessionRegistryMiddleware`
13. `PasswordChangeMiddleware`
14. `ConsentMiddleware`
15. `SecureCompanyMiddleware`
16. `SaasModuleMiddleware`
17. `GlobalRateLimitMiddleware`
18. `SecurityHeadersMiddleware`
19. `MessageMiddleware`
20. `XFrameOptionsMiddleware`

---

## 2. CONFIGURAÇÕES CRÍTICAS DJANGO

### 2.1 Settings de produção (positivos)

| Setting | Status | Referência |
|---------|--------|------------|
| `DEBUG=False` em prod | Enforced | `security_bootstrap.py:124-137` |
| `SECRET_KEY` validada (≥50 chars) | Enforced | `security_bootstrap.py:47-93` |
| `ALLOWED_HOSTS` sem `*` | Sim | `settings.py:43-47` |
| `SESSION_COOKIE_SECURE/HTTPONLY` | Sim (prod) | `settings.py:363-367` |
| `CSRF_COOKIE_SECURE/HTTPONLY` | Sim (prod) | `settings.py:371-373` |
| `SECURE_SSL_REDIRECT` | Sim (prod) | `settings.py:378` |
| `SECURE_HSTS_SECONDS` | 31536000 (prod) | `settings.py:379-386` |
| `SECURE_BROWSER_XSS_FILTER` | Sim | `settings.py:396-399` |
| `SECURE_CONTENT_TYPE_NOSNIFF` | Sim | `settings.py:396-399` |
| `X_FRAME_OPTIONS` | DENY | `settings.py:396-399` |
| CORS aberto | **Não configurado** (monólito same-site) | — |
| JWT | **Não implementado** | — |

### 2.2 Configurações inseguras

| Arquivo | Linha | Problema | Impacto | Solução |
|---------|-------|----------|---------|---------|
| `.gitignore` | 153-155 | `.env` **não** ignorado; só `.env.local` | Vazamento de todos os secrets se repo vazar | Adicionar `.env` ao gitignore; remover do histórico; rotacionar secrets |
| `.env` (versionado) | 7 | `SECRET_KEY` = placeholder conhecido | Sessões/forgery previsíveis | Gerar chave única ≥50 chars |
| `.env` (versionado) | 10 | `FIELD_ENCRYPTION_KEY` real commitada | Comprometimento = dados OLT/VPN/Telegram legíveis | Rotacionar + plano re-encrypt |
| `.env` (versionado) | 110 | `OPENROUTESERVICE_API_KEY` real | Abuso de quota/custo | Revogar no ORS; secret manager |
| `.env` (versionado) | 120 | `ALERT_BRIDGE_API_TOKEN` real | Acesso parcial ao bridge | Rotacionar token + HMAC |
| `.env` (versionado) | 126 | `BRIDGE_HMAC_SECRET` **vazio** | Anti-replay ausente ou bridge 503 em prod | Definir secret dedicado ≠ token |
| `settings.py` | 343-345 | Auto-adiciona `http://` em `CSRF_TRUSTED_ORIGINS` | CSRF cross-scheme | Em prod, só `https://` |
| `ftth_viewer/geocoding_privacy.py` | ~20 | Fallback salt dev conhecido | Reversão de hashes em dev | Definir `GEOCODING_CACHE_SALT` |
| `core/health_views.py` | 43-53 | `/health/security/` público | Reconhecimento de postura | Restringir IP interno |
| `core/health_views.py` | 25-27 | `/ready/` expõe erro DB | Info disclosure infra | Mensagem genérica externamente |
| `core/middleware_rate_limit_global.py` | 25-26 | Rate limit global off se `DEBUG=True` | Brute force em staging | `FORCE_RATE_LIMIT=true` |
| `core/login_lockout.py` | 24 | Lockout off em `DEBUG=True` | Idem | Idem |

### 2.3 Equivalente `python manage.py check --deploy`

| Check | Prod |
|-------|------|
| DEBUG desligado | Bloqueado bootstrap |
| SECRET_KEY forte | Validada |
| ALLOWED_HOSTS | Sem wildcard |
| SSL redirect + HSTS | Sim |
| Cookies seguros | Sim |
| CSRF ativo | Sim |
| Clickjacking | DENY |
| Mídia pública Django | Bloqueada bootstrap |

CI: `.github/workflows/security.yml:33` executa `check --deploy`; Bandit/pip-audit com `|| true` **não bloqueiam merge**.

---

## 3. DADOS PESSOAIS

| Dado | Model | Endpoint / exposição | Serializer / view |
|------|-------|----------------------|-------------------|
| Nome, e-mail, telefone | `CustomUser` | CRUD empresa, `/api/v1/users/` | `UserSerializer` (`core/serializers.py:30-42`) |
| E-mail, telefone, endereço | `Company` | `/api/v1/companies/` | `CompanySerializer` (CNPJ mascarado) |
| CNPJ (PJ) | `Company.cnpj` | Admin RM; API só `cnpj_masked` | `EncryptedCharField` |
| IP + User-Agent | `ConsentRecord` | Portal consentimento | — |
| IP | `SecurityAuditEvent`, `UserSessionRecord`, `TrustedDevice` | Auditoria interna | Sanitizado (`audit_trail.py`) |
| Telefones WhatsApp | `AlertBridgeConfig`, `WhatsAppLine` | Bridge worker API | Texto plano |
| Lat/lon | `GeocodingCache`, `ViabilidadeCache` | APIs FTTH | Geocoding: hash SHA-256, sem endereço completo |
| Texto livre (PII) | `Ticket`, `TicketMessage` | Suporte | Export LGPD inclui tickets |
| Credenciais OLT/VPN | `OltEquipment`, `CompanyVpnConfig` | Módulo OLT | Criptografado |
| SN ONU | `OnuCleanupJob.serial_numbers` | Jobs OLT | Logs operacionais |

**CPF:** não encontrado. **Biometria, saúde, selfies:** não encontrados.

---

## 4. APIs E DRF

### 4.1 Autenticação e permissões

- **SessionAuthentication** apenas — sem JWT, sem `AllowAny` em ViewSets
- Default: `IsAuthenticated` (`settings.py:222-224`)
- Tenant scoping via queryset + testes (`core/tests_api_tenant.py`)

### 4.2 Endpoints DRF (`/api/v1/`)

| Recurso | Leitura | Escrita |
|---------|---------|---------|
| `companies` | `IsAuthenticated` + queryset | RM: `IsRMAdmin`; admin: `IsCompanyAdmin` |
| `maps` | `IsAuthenticated` + queryset | `IsCompanyAdmin` |
| `users` | `IsAuthenticated` + queryset | `IsCompanyAdmin` |
| `schema`, `docs` | Qualquer autenticado | — |

**Risco:** leituras usam só queryset (sem `TenantScopedPermission` object-level) — mitigado por testes.

### 4.3 APIs inseguras / superfície crítica

| Endpoint | Auth | Problema | Risco |
|----------|------|----------|-------|
| `GET /health/security/` | Nenhuma | Expõe flags MFA, CSP, encryption | Reconhecimento |
| `GET /ready/` | Nenhuma | Erro DB parcial | Info disclosure |
| `GET /api/internal/alert-bridge/configs/` | IP + token + HMAC | Payload com `telegram_bot_token` multi-tenant | **Crítico** se secret vazar |
| `POST /api/webhooks/asaas/` | Token (`csrf_exempt`) | Altera billing / `is_active` | Financeiro |
| `GET/POST /api/v1/*` | Sessão | Isento MFA, consent, troca senha | Bypass controles web |
| `POST .../api/cache/geocoding/clear` | `@login_required` | Apaga cache **global** | DoS funcional |
| `GET /media/` (prod) | Login + tenant | Protegido via Django | OK |

### 4.4 Isenções de middleware em `/api/v1/`

| Middleware | Linha | Efeito |
|------------|-------|--------|
| `ConsentMiddleware` | `middleware_consent.py:29` | API sem consentimento LGPD |
| `MfaEnforcementMiddleware` | `middleware_mfa.py:22` | API sem MFA |
| `PasswordChangeMiddleware` | `middleware_password_change.py:40` | API com senha temporária |

---

## 5. BANCO DE DADOS

| Aspecto | Status |
|---------|--------|
| Campos sensíveis criptografados | CNPJ, Telegram, senhas OLT/VPN |
| Campos texto plano | E-mail, telefone, endereço, telefones WhatsApp |
| Raw SQL | Parametrizado (`health_views.py:22`; tests) — sem concatenação |
| SQL injection | Risco baixo (ORM predominante) |
| Soft delete | Usuário: anonimização; empresa: sem fluxo automático |

---

## 6. LGPD

### 6.1 Implementado

| Funcionalidade | Arquivo / rota |
|----------------|----------------|
| Consentimento versionado | `ConsentRecord`, `middleware_consent.py`, `/consent-required/` |
| Portal do titular | `/meus-dados/` → `core/lgpd_views.py` |
| Export portabilidade | `core/lgpd_export.py` (JSON/CSV/ZIP assinado) |
| Eliminação (usuário) | `my_data_delete_request` + `process_data_subject_requests` |
| Anonimização | `core/lgpd_anonymization.py` |
| Retenção / purge | `core/lgpd_retention.py`, crons `scripts/cron-lgpd-*.sh` |
| ROPA / inventário | `lgpd_data_inventory`, `lgpd_compliance_report` |
| DPO | `/encarregado-dados/` |
| Geocoding minimizado | `GeocodingCache` — hash SHA-256, sem endereço completo |

### 6.2 Gaps

| Gap | Artigo | Evidência |
|-----|--------|-----------|
| Retificação sem fluxo UI | Art. 18, III | `DataSubjectRequest` tipo `rectify` sem portal |
| API isenta de consentimento | Art. 8 | `middleware_consent.py:29` |
| Export admin sem trilha DSR | Art. 18, II | `core/views.py:1874+` |
| Eliminação não cobre `Company` | Art. 18, VI | `lgpd_anonymization.py` só usuário |
| Telefones WhatsApp texto plano | Art. 46 | `alerts/models.py` |
| Logs com senhas em DEBUG | Art. 46 | `core/views.py:355, 1467` |

---

## 7. LOGS

| Local | Risco | Linha |
|-------|-------|-------|
| `SanitizingFilter` global | Mascara e-mail/CNPJ | `core/log_sanitizer.py`, `logging_config.py` |
| `core/views.py` POST.dict | **Senhas em DEBUG** | 355, 1467 |
| `core/password_reset.py` | E-mail em info (mascarado) | ~130, 292 |
| Nginx access logs | IPs, query strings | `nginx.conf:29` |
| OLT `log_output` | Credenciais possíveis | `operational_sanitizer.py` |

---

## 8. UPLOADS

| Controle | Status | Arquivo |
|----------|--------|---------|
| Extensões permitidas | `.xlsx`, `.xls`, `.csv`, `.kml`, `.kmz` | `core/upload_security.py:27-28` |
| Nome aleatório | Sim | `secure_upload_filename()` |
| Quarentena | Sim | `quarantine_file()` |
| ClamAV opcional | Sim | `scan_file_with_clamav()` |
| Limite tamanho | Nginx 100M | `nginx.conf:20` |
| Mídia pública | **Não** (proxy autenticado) | `nginx.conf:40-49`, `media_protected.py` |
| Path traversal | Bloqueado | `media_protected.py:30-43` |

---

## 9. AUTENTICAÇÃO

| Controle | Status | Referência |
|----------|--------|------------|
| Login rate limit | 20/15 min | `rate_limiting.py:100` |
| Lockout progressivo | 5/10/15 → 5/15/60 min | `login_lockout.py:15-16` |
| MFA TOTP | Sim; obrigatório prod | `MFA_REQUIRED` |
| MFA lockout | Sim | `core/mfa_lockout.py` |
| Sessão idle | 30 min | `SESSION_IDLE_TIMEOUT` |
| Reset / ativação conta | Token digest + rate limit | `activation_views.py` |
| Argon2 | Hasher primário | `settings.py:144-158` |
| Refresh token JWT | N/A (sessão) | — |

---

## 10. FRONTEND

| Item | Status |
|------|--------|
| XSS | CSP nonce + strict em prod; auto-escape Django |
| CSP | `core/security_headers.py` — `frame-ancestors 'none'` |
| Tokens em localStorage | **Não** — só tema e e-mail “lembrar” |
| Histórico FTTH | `sessionStorage` TTL, sem endereço completo |
| React/Next/Vue | **Não** — templates Django + JS |

---

## 11. FALHAS CRÍTICAS

| Severidade | Vulnerabilidade | Impacto | Arquivo | Linha |
|------------|-----------------|---------|---------|-------|
| **Crítica** | `.env` versionado com secrets reais | Vazamento total infra + criptografia | `.env` | 7, 10, 110, 120 |
| **Crítica** | Bridge API retorna `telegram_bot_token` multi-tenant | Compromisso de todos os bots | `alerts/models.py` | ~112 |
| **Alta** | `BRIDGE_HMAC_SECRET` vazio no `.env` | Anti-replay ausente | `.env` | 126 |
| **Alta** | Webhook Asaas (`csrf_exempt`) | Suspensão/ativação indevida tenants | `core/billing/asaas_webhook.py` | 59-91 |
| **Alta** | Log `request.POST.dict()` | Senhas em log DEBUG | `core/views.py` | 355, 1467 |
| **Média** | `/api/v1/` isento MFA/consent/senha | Bypass controles web | middlewares | ver §4.4 |
| **Média** | Cache geocoding clear global | DoS funcional | `ftth_viewer/views.py` | 778-787 |
| **Média** | Export CSV usuários sem DSR | Accountability | `core/views.py` | 1874-1892 |
| **Baixa** | Token Asaas em query string | Vazamento logs/referrers | `asaas_webhook.py` | 26-27 |

---

## 12. OWASP TOP 10 (2021)

| ID | Classificação | Evidência |
|----|---------------|-----------|
| A01 | Broken Access Control | Parcial — DRF tenant OK; gaps cache global, Swagger |
| A02 | Cryptographic Failures | Mitigado Fernet; risco `.env` + SECRET_KEY placeholder |
| A03 | Injection | Baixo — ORM; upload bloqueia `eval(` |
| A04 | Insecure Design | Bridge multi-tenant; API bypass middleware |
| A05 | Security Misconfiguration | `.env` no Git; HMAC vazio; health público |
| A06 | Vulnerable Components | CI pip-audit/Bandit com `|| true` |
| A07 | Auth Failures | Lockout+MFA; off em DEBUG |
| A08 | Software/Data Integrity | Webhook Asaas; HMAC bridge |
| A09 | Logging Failures | Sanitizer OK; gap POST.dict |
| A10 | SSRF | Geocoding/OSRM externos |

---

## 13. TOKENS E CREDENCIAIS (no repositório)

| Tipo | Arquivo | Linha | Notas |
|------|---------|-------|-------|
| `SECRET_KEY` (placeholder) | `.env` | 7 | Valor na blocklist bootstrap |
| `FIELD_ENCRYPTION_KEY` | `.env` | 10 | **Real — rotacionar** |
| `OPENROUTESERVICE_API_KEY` | `.env` | 110 | **Real — rotacionar** |
| `ALERT_BRIDGE_API_TOKEN` | `.env` | 120 | **Real — rotacionar** |
| `BRIDGE_HMAC_SECRET` | `.env` | 126 | **Vazio** |
| CI secrets | `.github/workflows/*.yml` | 29-31 | Apenas CI, testing-only |
| Senhas teste | `core/tests*.py` | várias | Fixtures — OK |

> **Nota:** valores reais não são reproduzidos neste documento. Ver `docs/deploy/ROTACAO_SECRETS.md` para runbook.

---

## 14. BUSCAS AUTOMÁTICAS — RESUMO

| Padrão | Resultado |
|--------|-----------|
| `csrf_exempt` | 1 — webhook Asaas (esperado) |
| `AllowAny` | 0 |
| `DEBUG=True` hardcoded | Apenas testes/dev |
| `verify=False` | 0 em Python prod |
| `eval(` / `exec(` | Bloqueados em upload; legado em `archive/legacy-desktop-tools/` |
| `pickle.loads` | 0 |
| `subprocess` | OLT VPN, ClamAV, Docker — uso legítimo |
| `raw SQL` | Parametrizado |

---

## 15. RECOMENDAÇÕES

### Crítica (0–7 dias)

1. **Remover `.env` do Git** e rotacionar todos os secrets (ver `docs/deploy/ROTACAO_SECRETS.md`)
2. **Definir `BRIDGE_HMAC_SECRET`** dedicado (≠ `ALERT_BRIDGE_API_TOKEN`)
3. **Eliminar log de `request.POST.dict()`** ou redact campos `password*` (`core/views.py:355, 1467`)

### Alta (7–30 dias)

4. Restringir `/health/security/` e `/ready/` a IPs internos
5. Remover isenção de `/api/v1/` em MFA, consentimento e troca de senha
6. Proteger `api_cache_geocoding_clear` com admin + escopo empresa
7. Token Asaas somente via header (sem query string)
8. Registrar exports admin em audit/DSR

### Média (30–90 dias)

9. Fluxo de **retificação** LGPD (art. 18, III)
10. Criptografar telefones WhatsApp ou revisar retenção
11. Falhar CI em achados críticos Bandit/pip-audit
12. CSRF origins: só HTTPS em produção
13. Processo offboarding tenant (dados `Company`)

### Baixa

14. Corrigir inventário ROPA (`lgpd_data_inventory.py`)
15. Restringir Swagger a RM/admin
16. WAF / rate limit nginx na borda

---

## 16. HARDENING DJANGO SUGERIDO

| Área | Sugestão |
|------|----------|
| Headers | Manter CSP strict; adicionar `Permissions-Policy` |
| Middleware | Lista única auditável de isenções API |
| Secrets | Vault / secrets do servidor — nunca no Git |
| Criptografia | Plano rotação `FIELD_ENCRYPTION_KEY` |
| Arquitetura | Bridge: tokens scoped por tenant |
| Monitoramento | Sentry + `check_bridge_health` + crons LGPD |
| CI | Remover `|| true` em security.yml para achados críticos |

---

## 17. CONCLUSÃO

O projeto está **materialmente acima da média** para SaaS Django B2B multi-tenant: bootstrap de segurança, MFA, LGPD estruturado, mídia protegida, criptografia seletiva e testes de isolamento tenant.

O **principal risco** não é ausência de controles no código, e sim **gestão de secrets** (`.env` versionado) combinado com **endpoint bridge multi-tenant** e **brechas de middleware na API REST**.

**Prioridade zero:** tratar `.env` no Git como incidente de segurança, rotacionar credenciais e validar deploy checklist antes de produção.

---

*Relatório gerado em 23/05/2026 — auditoria read-only do repositório.*
