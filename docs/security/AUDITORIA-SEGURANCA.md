# Auditoria de Segurança — SaaS Verificador de Viabilidade

> **Data da análise:** 26/05/2026  
> **Escopo:** Django, API REST, multi-tenant, infra, CI/CD, integrações  
> **Security Score:** **64 / 100**

---

## Índice

1. [Resumo executivo](#resumo-executivo)
2. [Ranking de criticidade](#ranking-de-criticidade)
3. [Vulnerabilidades detalhadas](#vulnerabilidades-detalhadas)
4. [Endpoints mais perigosos](#endpoints-mais-perigosos)
5. [Quick wins](#quick-wins)
6. [Checklist OWASP Top 10](#checklist-owasp-top-10)
7. [Checklist Django Security](#checklist-django-security)
8. [Pontos positivos](#pontos-positivos)
9. [Cadeias de ataque reais](#cadeias-de-ataque-reais)
10. [Arquitetura vulnerável](#arquitetura-vulnerável)
11. [Recomendações enterprise](#recomendações-enterprise)
12. [Plano de ação sugerido](#plano-de-ação-sugerido)

---

## Resumo executivo

O projeto possui **muitos controles enterprise** já implementados (bootstrap de produção, CSP, MFA, criptografia de campos, bridge HMAC, mídia protegida, lockout de login). Porém existem **falhas exploráveis em produção**, sendo a mais grave o arquivo **`.env` versionado no Git com chaves reais**.

| Área | Nota (0–100) |
|------|:------------:|
| Configuração Django | 78 |
| Autenticação / Autorização | 62 |
| Isolamento multi-tenant | 70 |
| API REST (DRF) | 55 |
| Gestão de segredos | **35** |
| Infra / CI | 58 |
| Upload / input | 72 |
| Observabilidade | 65 |
| **Média ponderada** | **64** |

---

## Ranking de criticidade

| # | Severidade | Problema | Arquivo / endpoint principal |
|:-:|------------|----------|------------------------------|
| 1 | CRITICAL | `.env` com segredos reais no Git | `.env`, `.gitignore` |
| 2 | CRITICAL | Open redirect no login RM (`next`) | `core/views.py` → `POST /rm/login/` |
| 3 | HIGH | MFA não aplicado à API `/api/v1/` | `core/middleware_mfa.py` |
| 4 | HIGH | Token webhook Asaas via query string | `core/billing/asaas_webhook.py` |
| 5 | HIGH | Spoofing de `X-Forwarded-For` (lockout/sessão) | `core/login_lockout.py`, `session_security.py` |
| 6 | HIGH | Path disclosure na API FTTH | `ftth_viewer/views.py` → `api_arquivos` |
| 7 | HIGH | Limpeza global de cache por qualquer user | `api_cache_geocoding_clear` |
| 8 | HIGH | Swagger aberto para usuários autenticados | `GET /api/v1/docs/` |
| 9 | HIGH | `reset_superuser` sem guarda de produção | `management/commands/reset_superuser.py` |
| 10 | MEDIUM | `COMPANY_USER` lista usuários via API | `core/api.py` → `UserViewSet` |
| 11 | MEDIUM | Escalação de role via API (COMPANY_ADMIN) | `core/serializers.py` |
| 12 | MEDIUM | Enumeração de e-mail no login | `rm_login_view`, `company_login_view` |
| 13 | MEDIUM | Erro 500 com `str(e)` na API FTTH | `ftth_viewer/views.py` |
| 14 | MEDIUM | Rate limit desligado em `DEBUG=True` | middleware / lockout |
| 15 | MEDIUM | CI não bloqueia (`pip-audit`, `bandit` com `\|\| true`) | `.github/workflows/security.yml` |
| 16 | MEDIUM | Fernet fallback para `SECRET_KEY` | `core/field_encryption.py` |
| 17 | LOW | `/health/security/` expõe flags | `core/health_views.py` |
| 18 | LOW | `requirements.txt` sem pins de versão | `requirements.txt` |

---

## Vulnerabilidades detalhadas

### Legenda de severidade

| Nível | Significado |
|-------|-------------|
| CRITICAL | Exploração imediata; impacto total ou vazamento massivo de segredos |
| HIGH | Exploração realista; bypass de controles ou DoS cross-tenant |
| MEDIUM | Exfiltração limitada, escalação parcial ou misconfig |
| LOW | Reconhecimento, hardening ou débito técnico |

---

### CRITICAL-01 — `.env` versionado no Git

| Campo | Conteúdo |
|-------|----------|
| **Problema** | Arquivo `.env` com API keys reais commitado no repositório |
| **Local** | `.env` (rastreado por `git ls-files`), `.gitignore` não ignora `.env` |
| **Exploração** | Acesso ao repo → chaves Resend, OpenRouteService, DB, etc. |
| **Impacto** | Fraude, phishing, abuso de APIs, comprometimento de integrações |
| **Correção** | `git rm --cached .env`, adicionar ao `.gitignore`, **rotacionar todas as chaves**, auditar histórico Git |

```bash
# Ações imediatas
git rm --cached .env
echo ".env" >> .gitignore
# Rotacionar: RESEND_API_KEY, OPENROUTESERVICE_API_KEY, SECRET_KEY, FIELD_ENCRYPTION_KEY, etc.
```

---

### CRITICAL-02 — Open redirect no login RM

| Campo | Conteúdo |
|-------|----------|
| **Problema** | Parâmetro `next` redireciona sem validação de host |
| **Local** | `core/views.py` → `rm_login_view` (linhas ~165–169) |
| **Endpoint** | `POST /rm/login/?next=https://evil.com` |
| **Exploração** | Link de phishing pós-login legítimo |
| **Impacto** | Roubo de credenciais em site falso, abuso de confiança da marca |

**Correção sugerida:**

```python
from django.utils.http import url_has_allowed_host_and_scheme

next_url = request.GET.get("next") or request.POST.get("next")
if next_url and url_has_allowed_host_and_scheme(
    url=next_url,
    allowed_hosts={request.get_host(), *settings.ALLOWED_HOSTS},
    require_https=request.is_secure(),
):
    return redirect(next_url)
return redirect("dashboard")
```

---

### HIGH-01 — MFA bypass na API REST

| Campo | Conteúdo |
|-------|----------|
| **Problema** | `/api/v1/` está em `EXEMPT_PREFIXES` do `MfaEnforcementMiddleware` |
| **Local** | `core/middleware_mfa.py` |
| **Exploração** | Cookie de sessão roubado → CRUD na API sem TOTP |
| **Impacto** | Bypass de MFA para operações administrativas |

**Correção:** Remover isenção ou adicionar `MfaVerifiedPermission` no DRF.

---

### HIGH-02 — Token Asaas na query string

| Campo | Conteúdo |
|-------|----------|
| **Problema** | `request.GET.get("token")` aceito no webhook |
| **Local** | `core/billing/asaas_webhook.py` → `_webhook_token_ok` |
| **Endpoint** | `POST /api/webhooks/asaas/?token=...` |
| **Exploração** | Token em logs de proxy/CDN → forjar eventos de pagamento |
| **Impacto** | Suspender/reativar empresas indevidamente |

**Correção:** Aceitar apenas headers `asaas-access-token` / `X-Asaas-Token`.

---

### HIGH-03 — Spoofing de X-Forwarded-For

| Campo | Conteúdo |
|-------|----------|
| **Problema** | XFF usado sem verificar se `REMOTE_ADDR` é proxy confiável |
| **Local** | `login_lockout.py`, `session_security.py`, `account_activation.py` |
| **Exploração** | Header `X-Forwarded-For: 1.2.3.4` → bypass lockout / session bind IP |
| **Impacto** | Brute force mais eficaz; sessões não encerram ao mudar IP real |

**Correção:** Reutilizar lógica de `bridge_security.get_bridge_client_ip()` com `TRUST_X_FORWARDED_FOR`.

---

### HIGH-04 — Exposição de caminhos de arquivo (FTTH)

| Campo | Conteúdo |
|-------|----------|
| **Problema** | API retorna `mapa.file.path` (caminho absoluto no servidor) |
| **Local** | `ftth_viewer/views.py` → `api_arquivos` |
| **Endpoint** | `GET /{slug}/verificador/api/arquivos` |
| **Exploração** | Reconhecimento de paths (`/var/www/...`) |
| **Impacto** | Facilita path traversal e ataques direcionados |

**Correção:** Retornar apenas `id`, `nome`, `tipo` + URL assinada de download.

---

### HIGH-05 — Cache geocoding apagado por qualquer usuário

| Campo | Conteúdo |
|-------|----------|
| **Problema** | `GeocodingCache.objects.all().delete()` sem checagem de role |
| **Local** | `ftth_viewer/views.py` → `api_cache_geocoding_clear` |
| **Endpoint** | `POST .../verificador/api/cache/geocoding/clear` |
| **Exploração** | `COMPANY_USER` autenticado limpa cache global |
| **Impacto** | DoS cross-tenant; custo extra em APIs externas |

**Correção:** Exigir `is_rm_admin` ou `is_company_admin`.

---

### HIGH-06 — Swagger / OpenAPI exposto

| Campo | Conteúdo |
|-------|----------|
| **Problema** | `/api/v1/docs/` acessível a qualquer sessão autenticada |
| **Local** | `core/api_urls.py` |
| **Exploração** | Mapeamento automatizado da superfície de ataque |
| **Impacto** | Acelera ataques de IDOR e automação |

**Correção:** Proteger com `IsRMAdmin` ou desabilitar rota em produção.

---

### HIGH-07 — Comando `reset_superuser` sem proteção

| Campo | Conteúdo |
|-------|----------|
| **Problema** | Management command cria superuser sem validar ambiente |
| **Local** | `core/management/commands/reset_superuser.py` |
| **Exploração** | Shell na VPS → `python manage.py reset_superuser email senha` |
| **Impacto** | Takeover total da plataforma |

**Correção:** Bloquear em `IS_PRODUCTION`; exigir token one-time.

---

### MEDIUM-01 — API: COMPANY_USER lista usuários

| Campo | Conteúdo |
|-------|----------|
| **Problema** | `UserViewSet` usa só `IsAuthenticated` em `list`/`retrieve` |
| **Local** | `core/api.py` |
| **Dados expostos** | email, role, last_login, company (via `UserSerializer`) |
| **Correção** | Exigir `IsCompanyAdmin` ou endpoint `/me` para usuário comum |

---

### MEDIUM-02 — Escalação de role via API

| Campo | Conteúdo |
|-------|----------|
| **Problema** | `validate_role` bloqueia apenas `RM`, não impede promoção a `COMPANY_ADMIN` |
| **Local** | `core/serializers.py` |
| **Correção** | Apenas RM altera `role`; admin de empresa não muda role de terceiros |

---

### MEDIUM-03 — Enumeração de usuários no login

| Campo | Conteúdo |
|-------|----------|
| **Problema** | `CustomUser.objects.get(email__iexact=...)` antes do authenticate |
| **Local** | `rm_login_view`, `company_login_view` |
| **Correção** | Mensagens uniformes; delay constante; evitar lookup explícito por e-mail |

---

### MEDIUM-04 — Vazamento em erros JSON (FTTH)

| Campo | Conteúdo |
|-------|----------|
| **Problema** | `JsonResponse({"erro": f"Erro interno: {str(e)}"})` |
| **Correção** | Log no servidor; resposta genérica ao cliente |

---

### MEDIUM-05 — CI de segurança não bloqueante

| Campo | Conteúdo |
|-------|----------|
| **Problema** | `pip-audit ... \|\| true` e `bandit ... \|\| true` |
| **Local** | `.github/workflows/security.yml` |
| **Correção** | Remover `\|\| true`; falhar pipeline em achados HIGH+ |

---

### LOW-01 — Endpoint `/health/security/`

Expõe flags (`mfa_required`, `csp_strict`, `field_encryption_configured`) — útil para reconhecimento. Restringir por IP ou autenticação interna.

---

## Endpoints mais perigosos

| Prioridade | Método | Endpoint | Risco principal |
|:----------:|--------|----------|-----------------|
| P0 | POST | `/api/webhooks/asaas/` | CSRF exempt; forja billing |
| P0 | GET | `/api/internal/alert-bridge/configs/` | Tokens Telegram em plaintext (se HMAC/IP falhar) |
| P1 | * | `/api/v1/users/`, `/companies/`, `/maps/` | IDOR; MFA bypass |
| P1 | GET | `/api/v1/docs/` | Reconhecimento completo da API |
| P1 | POST | `/rm/login/` | Open redirect via `next` |
| P2 | GET/POST | `/ativar-conta/<token>/` | Account takeover se token vazar |
| P2 | POST | `.../api/cache/geocoding/clear` | DoS cross-tenant |
| P2 | GET | `.../api/arquivos` | Path disclosure |
| P2 | GET | `/media-signed/<token>/` | Acesso a arquivo se token vazar |
| P3 | * | OLT Docker worker | RCE lateral se socket Docker comprometido |

---

## Quick wins

Tarefas de **1 a 3 dias** com alto retorno:

- [ ] **P0** — Remover `.env` do Git e rotacionar todas as chaves
- [ ] **P0** — Adicionar `.env` ao `.gitignore`
- [ ] **P1** — Corrigir open redirect (`url_has_allowed_host_and_scheme`)
- [ ] **P1** — Remover `GET token` do webhook Asaas
- [ ] **P1** — Remover campo `caminho` de `api_arquivos`
- [ ] **P1** — Restringir `api_cache_geocoding_clear` a admins
- [ ] **P1** — Unificar lógica de IP (XFF só com proxy confiável)
- [ ] **P2** — Proteger ou desabilitar `/api/v1/docs/` em produção
- [ ] **P2** — CI: falhar em `security-check.sh`, `pip-audit`, `bandit`
- [ ] **P2** — Bloquear `reset_superuser` em produção

---

## Checklist OWASP Top 10

| ID | Categoria | Status | Observação |
|----|-----------|:------:|------------|
| A01 | Broken Access Control | ⚠️ | Gaps na API DRF + cache clear |
| A02 | Cryptographic Failures | ⚠️ | `.env` leak; fallback Fernet |
| A03 | Injection | ✅ | ORM; cuidado `OLT_DOCKER_RUN_ARGS` |
| A04 | Insecure Design | ⚠️ | MFA/API desalinhados |
| A05 | Security Misconfiguration | ❌ | `.env` no Git; CI `|| true` |
| A06 | Vulnerable Components | ⚠️ | pip-audit não bloqueia |
| A07 | Identification & Auth Failures | ⚠️ | Open redirect; enumeração |
| A08 | Software & Data Integrity | ⚠️ | Webhook depende de token único |
| A09 | Security Logging Failures | ✅ | Audit trail presente |
| A10 | SSRF | ✅ | URLs fixas (ViaCEP, OSRM) |

**Legenda:** ✅ Adequado · ⚠️ Parcial · ❌ Crítico

---

## Checklist Django Security

| Controle | Produção | Dev |
|----------|:--------:|:---:|
| `DEBUG=False` | ✅ bootstrap | — |
| `SECRET_KEY` forte (≥50 chars) | ✅ | ⚠️ se vazada no Git |
| `ALLOWED_HOSTS` sem `*` | ✅ | ✅ |
| CSRF middleware ativo | ✅ | ✅ |
| `SESSION_COOKIE_SECURE` | ✅ | Lax |
| `SESSION_COOKIE_HTTPONLY` | ✅ | ✅ |
| `CSRF_COOKIE_HTTPONLY` | ✅ | configurável |
| `SECURE_SSL_REDIRECT` | ✅ | — |
| HSTS | ✅ | — |
| `X_FRAME_OPTIONS = DENY` | ✅ | ✅ |
| Mídia não pública | ✅ | opcional |
| Admin restrito (RM only) | ✅ | ✅ |
| Validators senha (min 14) | ✅ | ✅ |
| Argon2 hasher | ✅ | ✅ |

---

## Pontos positivos

Controles já bem implementados no projeto:

| Controle | Implementação |
|----------|---------------|
| Bootstrap de segurança | `saas_viabilidade/security_bootstrap.py` |
| Bloqueio DEBUG em VPS | `SecurityBootstrapError` |
| CSP com nonce | `middleware_csp.py`, `security_headers.py` |
| Bridge HMAC + anti-replay | `core/bridge_security.py` |
| Mídia protegida + anti traversal | `core/media_protected.py` |
| Upload seguro (nome aleatório, AV) | `core/upload_security.py` |
| Lockout progressivo | `core/login_lockout.py` |
| Sessão idle + revogação | `middleware_session_idle.py` |
| CNPJ criptografado + hash | `EncryptedCharField`, `cnpj_hash` |
| Sem CORS permissivo | django-cors-headers não usado |
| Testes de segurança | `tests_phase2/3_security.py` |

---

## Cadeias de ataque reais

```
┌─────────────────────────────────────────────────────────────────┐
│ CADEIA 1 — Leak de repositório                                  │
│ .env no Git → RESEND_API_KEY → phishing em massa                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ CADEIA 2 — Phishing pós-auth                                    │
│ ?next=https://evil.com → login RM OK → redirect malicioso       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ CADEIA 3 — Sessão roubada + API                                 │
│ XSS/malware → cookie sessão → /api/v1/users/ (sem MFA) → admin  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ CADEIA 4 — Webhook                                              │
│ token em log CDN → POST /api/webhooks/asaas/ → status billing   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ CADEIA 5 — Insider / usuário comum                              │
│ COMPANY_USER → POST cache/clear → DoS global geocoding          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ CADEIA 6 — Shell na VPS                                         │
│ RCE/metadados → manage.py reset_superuser → takeover total      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Arquitetura vulnerável

```
                    ┌──────────────┐
                    │   Nginx      │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
     .env no Git ──►│ Django WSGI  │◄── MFA não cobre /api/v1/
                    └──────┬───────┘
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │ PostgreSQL  │ │    Redis    │ │ Bridge API  │
    └─────────────┘ └─────────────┘ │ (tokens TG) │
                                    └──────┬──────┘
                                           │
                                    ┌──────▼──────┐
                                    │ Node Worker │
                                    └─────────────┘

    ┌─────────────────────────────────────────────┐
    │ OLT Docker (NET_ADMIN + SECRET_KEY injetada)│
    └─────────────────────────────────────────────┘
         ▲ elo mais frágil: segredos + exportação de credenciais
```

---

## Recomendações enterprise

| Prazo | Ação |
|-------|------|
| **Imediato** | Tratar `.env` no Git como incidente; rotacionar chaves |
| **1 semana** | Quick wins (redirect, webhook, API paths, cache clear) |
| **1 mês** | MFA na API; WAF; secrets manager (Vault / cloud SM) |
| **Trimestre** | Pentest multi-tenant; bug bounty; OAuth2/mTLS para integrações |
| **Contínuo** | SAST/SCA bloqueantes; testes IDOR automatizados; rotação de chaves |

### Gestão de segredos

- Nunca versionar `.env` — apenas `.env.example` sem valores reais
- Secret manager na VPS e no CI (GitHub Secrets)
- Rotação automática e auditoria de acesso

### Autenticação

- MFA obrigatório para `COMPANY_ADMIN` (`MFA_REQUIRED_COMPANY_ADMINS=True`)
- Aplicar MFA também no DRF (remover isenção `/api/v1/`)
- Validar `next` em todos os fluxos de login (incl. MFA)

### API

- Desabilitar Swagger em produção ou restringir a RM
- Revisar permissões de cada `ViewSet` action por action
- Considerar API tokens com escopo por tenant (futuro)

### Infra

- `server_tokens off` no Nginx
- Docker rootless; sem socket Docker no app server
- Rate limit na borda (CDN/WAF)

---

## Plano de ação sugerido

### Semana 1 — Contenção

| Dia | Tarefa | Responsável |
|-----|--------|-------------|
| D0 | Rotacionar chaves expostas no `.env` | DevOps |
| D0 | `git rm --cached .env` + `.gitignore` | Dev |
| D1 | Open redirect + webhook token | Dev |
| D2 | API arquivos + cache clear | Dev |
| D3 | XFF / IP confiável | Dev |
| D4 | CI security bloqueante | DevOps |
| D5 | Revisão + deploy | Todos |

### Semana 2–4 — Hardening

- MFA na API REST
- Swagger em produção
- `reset_superuser` protegido
- Permissões DRF (UserViewSet)
- Pentest interno nos fluxos multi-tenant

### Métricas de sucesso

- [ ] Security score ≥ 80
- [ ] Zero segredos no histórico Git (ou purge confirmado)
- [ ] CI vermelho em qualquer HIGH do Bandit/pip-audit
- [ ] Testes automatizados de IDOR tenant passando

---

## Referências no repositório

| Arquivo | Descrição |
|---------|-----------|
| `saas_viabilidade/security_bootstrap.py` | Validação de boot |
| `scripts/security-check.sh` | Scan local/CI |
| `.github/workflows/security.yml` | Pipeline de segurança |
| `core/tests_phase3_security.py` | Testes automatizados |
| `docs/security/cascavel-profile-rmsys.yaml` | Perfil de pentest |

---

*Documento gerado a partir da auditoria de segurança do codebase. Atualize este arquivo após cada correção implementada.*
