# READINESS TÉCNICO-OPERACIONAL — RM Systems (SaaS Verificador de Viabilidade)

> **Data da análise:** 25/05/2026  
> **Escopo:** arquitetura, segurança, banco, integrações, operação, deploy  
> **Modo:** somente leitura — nenhuma alteração de código, migrations ou credenciais  
> **Objetivo:** diagnóstico completo antes de correções em produção

---

## Visão geral

### Stack

| Camada | Tecnologia |
|--------|------------|
| Backend | Django 5.2, Python 3.12+ |
| Banco | PostgreSQL (obrigatório em produção via `DATABASE_URL`) |
| Cache | Redis opcional (`REDIS_URL`, `USE_REDIS_CACHE`) |
| Auth | Sessões Django + Argon2 + MFA TOTP (`django-otp`) |
| API | DRF + OpenAPI (`drf-spectacular`) |
| Frontend | Templates Django + JS vanilla + Bootstrap 5 + Leaflet |
| E-mail | Resend (backend custom) ou SMTP/console |
| Workers | Node.js (Alert Bridge / WhatsApp), Docker (OLT worker) |
| Deploy | VPS Linux — Nginx + Gunicorn + systemd |
| Monitoramento | Sentry, health checks, logs estruturados |

### Arquitetura macro

Monólito Django **multi-tenant por linha lógica** (`company_id` + slug na URL), não schema-per-tenant.

```
                    ┌─────────────────────────────────────┐
                    │           Nginx (HTTPS)             │
                    └─────────────────┬───────────────────┘
                                      │
                    ┌─────────────────▼───────────────────┐
                    │     Django (Gunicorn/Waitress)      │
                    │  ┌──────┬──────────┬────────┬──────┐ │
                    │  │ core │ftth_viewer│alerts│olt_ops│ │
                    │  └──┬───┴─────┬────┴──┬───┴──┬───┘ │
                    └─────┼─────────┼───────┼──────┼───────┘
                          │         │       │      │
              ┌───────────▼───┐ ┌───▼───┐ ┌─▼──┐ ┌─▼────────┐
              │  PostgreSQL   │ │ Redis │ │Node│ │Docker OLT│
              │   (Neon/VPS)  │ │(opt.) │ │Bridge│ worker  │
              └───────────────┘ └───────┘ └────┘ └──────────┘
                          │
              ┌───────────▼───────────────────────────────┐
              │ Resend, Sentry, Asaas, OSM, ViaCEP, ORS   │
              └───────────────────────────────────────────┘
```

**Apps Django e função:**

| App | Responsabilidade |
|-----|------------------|
| `saas_viabilidade` | Settings, URLs raiz, logging, Sentry, bootstrap de segurança |
| `core` | Tenant (`Company`), usuários, mapas CTO, tickets, LGPD, billing, quotas, RM admin |
| `ftth_viewer` | Verificador FTTH — mapa, geocoding, viabilidade, cache |
| `alerts` | Bridge Telegram→WhatsApp, config por empresa, API interna worker |
| `olt_ops` | OLT/ONU (Huawei/ZTE), VPN, fila de jobs CLI |

**Portais de acesso:**

| Portal | Prefixo | Público |
|--------|---------|---------|
| RM (admin global) | `/rm/` | Admins RM |
| Empresa (tenant) | `/{company_slug}/` | Usuários da empresa |
| API REST | `/api/v1/` | Autenticado + MFA |
| Verificador global | `/verificador/` | Legado/global |

### Maturidade geral

O sistema está **além de um MVP**: possui MFA, criptografia de campos, LGPD estruturado, quotas comerciais, módulos por plano, CI de segurança e documentação extensa. Porém a **maturidade operacional** ainda depende de processos manuais (onboarding, deploy VPS, workers externos, cron shell) e há **dívida de segurança** documentada (gestão de segredos, superfícies públicas, idempotência de webhooks).

**Classificação:** *Pré-produção enterprise* — controles avançados implementados, mas exige hardening e validação em ambiente real antes de escala comercial.

---

## Pontos fortes

1. **Hardening transversal** — 12+ middlewares customizados (CSP nonce, CRLF, rate limit global, tenant, módulos, sessão, MFA, consentimento LGPD).
2. **Multi-tenant estruturado** — `SecureCompanyMiddleware`, `TenantScopedPermission`, queryset filtrado por `company_id`, mídia protegida por empresa.
3. **Criptografia em repouso** — Fernet (`FIELD_ENCRYPTION_KEY`) para CNPJ, tokens Telegram, credenciais OLT/VPN.
4. **Autenticação robusta** — Argon2, senha mínima 14 chars, MFA TOTP, sessões concorrentes, bind IP, revogação, lockout de login.
5. **LGPD operacional** — consentimento versionado, DSR (export/delete), retenção, comandos de purge, auditoria.
6. **Modelo comercial** — planos P/M/G/XL com quotas e enforcement (`core/plans.py`, `core/quotas.py`).
7. **CI de segurança** — `check --deploy`, `check_security --strict`, pip-audit, Bandit, scan de padrões secretos.
8. **Documentação** — `docs/DOCUMENTACAO-TECNICA.md`, `docs/security/*`, `docs/deploy/*`, playbooks LGPD.
9. **Isolamento de módulos** — `SaasModuleMiddleware` bloqueia acesso a verificador/alertas/OLT conforme plano.
10. **Logs sanitizados** — filtro operacional, logs separados (app, audit, security, OLT).

---

## Pontos críticos

| # | Área | Problema | Impacto |
|---|------|----------|---------|
| 1 | Segredos | Histórico documentado de `.env` no Git; rotação pode estar pendente | Vazamento total de credenciais |
| 2 | Bridge | API interna devolve token Telegram **descriptografado** ao worker Node | Comprometimento de todos os bots se token/HMAC vazarem |
| 3 | Comandos | `reset_superuser` sem guarda de produção | Escalação total via shell na VPS |
| 4 | Webhook Asaas | Sem idempotência por ID de pagamento | Duplicidade de ativação/suspensão de tenant |
| 5 | Workers | Alert Bridge e OLT worker são processos **separados** — falha silenciosa se não monitorados | Alertas/WhatsApp/OLT param sem aviso claro ao cliente |
| 6 | Deploy | Script manual (`deploy_vps.sh`); sem pipeline CD automatizado para produção | Erro humano, rollback lento |
| 7 | Dependências | `requirements.txt` sem pins de versão | Supply chain / regressões imprevisíveis |
| 8 | FIELD_ENCRYPTION_KEY | Dados legados criptografados com chave inválida/antiga não descriptografam | Perda operacional de configs (CNPJ, tokens) |

---

## Riscos imediatos

*(Ação recomendada antes ou logo após go-live)*

1. **Rotacionar todos os segredos** se `.env` já foi commitado — ver `docs/deploy/ROTACAO_SECRETS.md`.
2. **Restringir `/health/security/`** via `HEALTH_SECURITY_ALLOWED_IPS` em produção.
3. **Proteger `reset_superuser`** — bloquear em produção ou exigir confirmação interativa + audit.
4. **Validar `FIELD_ENCRYPTION_KEY`** com `python manage.py setup_p1_security --write-key` e re-salvar campos criptografados legados.
5. **Monitorar workers** — cron/systemd para `check_bridge_health`; alertas Sentry se bridge stale.
6. **Confirmar mídia não pública** — `curl -I /media/cto_maps/...` deve retornar 302/403, não 200.
7. **Asaas webhook** — token forte no header; HTTPS obrigatório; considerar dedup por `payment.id`.

---

## Riscos ocultos

1. **Resend em modo teste** (`onboarding@resend.dev`) — e-mails não chegam a destinatários não verificados; parece “bug” operacional.
2. **Redis ausente** — rate limit, lockout, nonce bridge e fila OLT degradam para cache local (não compartilhado entre workers Gunicorn).
3. **Múltiplos workers Gunicorn** — fila OLT em DB + lock cache; mutex VPN pode serializar demais ou falhar sem Redis.
4. **Sessões WhatsApp Baileys** — disco local em `MENSAGENS/data/`; perda no redeploy exige re-pareamento QR.
5. **Open redirect** — mitigado com `safe_redirect` no login RM; validar também login empresa.
6. **Fernet fallback para SECRET_KEY** — opt-in perigoso se ativado em produção.
7. **Migrations com seeds** — `0005_add_rm_superusers` cria superusers via env só em DEBUG; revisar flags antes de migrate em staging.
8. **CNPJ legado** — registros criptografados antes da chave correta exigem re-save manual no painel.

---

## Segurança

### Gestão de segredos

| Variável | Onde | Risco |
|----------|------|-------|
| `SECRET_KEY` | `.env` | Crítico — sessões, tokens |
| `FIELD_ENCRYPTION_KEY` | `.env` | Crítico — todos os campos Fernet |
| `DATABASE_URL` | `.env` | Crítico |
| `RESEND_API_KEY` | `.env` | Alto |
| `ALERT_BRIDGE_API_TOKEN` | `.env` | Alto — acesso configs bridge |
| `BRIDGE_HMAC_SECRET` | `.env` | Alto |
| `ASAAS_WEBHOOK_TOKEN` | `.env` | Alto — billing |
| `ASAAS_API_KEY` | `.env` | Médio — pouco uso outbound no código |
| `OPENROUTESERVICE_API_KEY` | `.env` | Baixo |
| Credenciais OLT/VPN | PostgreSQL (encrypted) | Alto — acesso DB = acesso OLT |
| Token Telegram | PostgreSQL (encrypted) | Alto — exposto em trânsito ao worker |
| Sessão WhatsApp | Disco Node | Alto — não criptografado em repouso no worker |

**Hardcoded encontrado (baixo risco):** senhas em testes (`core/tests_*.py`), `debug_login.py` (bloqueado fora DEBUG), legado `archive/legacy-desktop-tools/`.

**`.env.example`:** contém placeholders fracos (`senha123`) — risco de cópia literal em dev.

### Autenticação e autorização

- **HTML:** `@login_required` + decorators `rm_admin_required`, `company_access_required`.
- **API DRF:** `IsAuthenticated` + `MfaVerifiedPermission` + throttling.
- **Tenant:** `TenantScopedPermission`, queryset por `company_id`.
- **MFA:** obrigatório em produção (`MFA_REQUIRED`); exempt em login, health, ativação.

### Endpoints públicos (superfície de ataque)

| Rota | Proteção | Nota |
|------|----------|------|
| `GET /health/`, `/ready/` | Nenhuma | Liveness/readiness |
| `GET /health/security/` | IP opcional | Expõe flags se aberto |
| `POST /api/webhooks/asaas/` | Token header | `csrf_exempt` |
| `GET /api/internal/alert-bridge/configs/` | Token + HMAC + IP | Devolve secrets Telegram |
| `GET|POST /ativar-conta/<token>/` | Token único + rate limit | OK |
| Login / password reset | Rate limit + lockout | OK |
| Páginas legais, DPO | Público | Esperado |

### Multi-tenant

**Modelo:** shared database, isolamento por `company_id` + slug URL + middleware.

**Controles:** API queryset, object permission, upload paths, mídia assinada, rate limit por empresa.

**Riscos residuais:** bugs de queryset sem filtro (histórico corrigido em UserViewSet); cache global geocoding (rotas admin-only para clear).

### Score segurança: **64 / 100**

*(Alinhado à auditoria em `docs/security/AUDITORIA-SEGURANCA.md` — maio/2026)*

| Subárea | Nota |
|---------|------|
| Configuração Django | 78 |
| Auth / Autorização | 62 |
| Multi-tenant | 70 |
| API REST | 55 |
| Gestão de segredos | **35** |
| Infra / CI | 58 |
| Upload / input | 72 |
| Observabilidade | 65 |

---

## Deploy

### Infraestrutura alvo

- **VPS Linux** (documentado: Hostinger)
- **Nginx** → proxy para Gunicorn
- **PostgreSQL** local ou Neon
- **Redis** recomendado em produção
- **Certbot** para TLS
- **systemd** para Gunicorn

### Arquivos de deploy

| Arquivo | Função |
|---------|--------|
| `setup_vps.sh` | Dependências sistema (1ª vez) |
| `setup-env.sh` | Cria `.env` |
| `deploy_vps.sh` | Pull, migrate, collectstatic, restart |
| `nginx.conf` | Proxy + estáticos |
| `gunicorn.service` | Unit systemd |
| `backup-db.sh` | Backup PG + GPG opcional |

### CI/CD

| Workflow | Trigger | Ações |
|----------|---------|-------|
| `.github/workflows/tests.yml` | push/PR | Testes Django (SQLite CI) |
| `.github/workflows/security.yml` | push/PR + cron semanal | check --deploy, check_security, pip-audit, Bandit, security-check.sh |

**Gap:** CI valida qualidade, mas **deploy em produção é manual** (`git pull` + `deploy_vps.sh`). Não há rollback automatizado, blue/green ou canary.

### Logs e monitoramento

- **Logs:** `logs/app.log`, `audit.log`, `security.log`, `olt_operations.log`
- **Sentry:** erros Django + bridge stale
- **Health:** `/health/`, `/ready/`, `/health/security/`
- **Bridge:** `check_bridge_health` + `AlertBridgeWorkerStatus`

### Backup e restore

- Script `backup-db.sh` — retenção 7 dias, GPG opcional
- **Gap:** restore documentado parcialmente; sem teste automatizado de restore
- Mídia (`VPS_MEDIA_ROOT`) — backup separado não scriptado no repo

### Score deploy: **58 / 100**

Scripts existem e são usáveis, mas operação depende de SSH manual, workers externos fora do systemd principal, e rollback é “git revert + redeploy”.

---

## Banco

### Modelos críticos

```
Company (raiz tenant)
├── CustomUser (role: RM | COMPANY_ADMIN | COMPANY_USER)
├── CompanyBilling (Asaas / manual)
├── CTOMapFile (mapas KML/KMZ)
├── Ticket → TicketMessage → TicketNotification
├── ConsentRecord, DataSubjectRequest (LGPD)
├── UserSessionRecord, TrustedDevice (sessão/MFA)
├── AccountActivationToken
└── SecurityAuditEvent

AlertBridgeConfig (1:1 Company) → WhatsAppLine
OltEquipment, CompanyVpnConfig, OnuCleanupJob (olt_ops)
GeocodingCache, ViabilidadeCache (ftth_viewer)
```

### Dados sensíveis persistidos

| Campo | Modelo | Proteção |
|-------|--------|----------|
| `password` (hash) | CustomUser | Argon2 |
| `cnpj` | Company | EncryptedCharField + hash |
| `telegram_bot_token` | AlertBridgeConfig | EncryptedCharField |
| OLT/VPN passwords | olt_ops | EncryptedCharField |
| `session_key`, `access_token_digest` | UserSessionRecord | Digest, não plaintext |
| `token_digest` | AccountActivationToken | SHA digest |
| `analysis_results` | CTOMapFile | JSON — dados de rede |

### Migrations importantes

| Migration | Significado |
|-----------|-------------|
| `0018`, `0020` | CNPJ criptografado |
| `0005` (olt_ops), `0008` (alerts) | Credenciais OLT/VPN/Telegram criptografadas |
| `0022`, `0026` | Sessões enterprise + access token |
| `0024`, `0025` | Planos e billing |
| `0016` | Ativação por link |
| `0004`, `0005` (core) | Seeds fibramar / RM superusers (dev) |

### Riscos de consistência

1. **Sem Celery** — jobs OLT em thread/DB; crash mid-job pode deixar status inconsistente.
2. **Fila OLT** — lock via cache; sem Redis, workers Gunicorn não compartilham lock corretamente.
3. **Billing webhook** — reaplicação de eventos Asaas sem dedup.
4. **Chave Fernet rotacionada** — dados antigos ilegíveis até re-save.
5. **Migration pendente** — `0026_usersessionrecord_access_token` mencionada em conversas anteriores; validar `migrate` em cada ambiente.

### Score banco: **72 / 100**

Modelagem sólida, criptografia seletiva, índices de performance; gaps em jobs assíncronos e idempotência de integrações.

---

## Integrações

### Mapa resumo

| Integração | Auth | Token storage | Retry | Idempotência | Falha |
|------------|------|---------------|-------|--------------|-------|
| **OLT (SSH)** | User/senha equipamento | DB encrypted | Re-enfileira se slot busy | Fila dedup por operação | Job `failed` + log |
| **VPN** | OVPN/PSK/user | DB encrypted | Poll TCP 2s até timeout | Mutex por slot | `VpnConnectionError` |
| **Telegram** | Bot token | DB → JSON worker | Poll configs 15s | Nonce HMAC | `last_error` config |
| **WhatsApp (Baileys)** | Sessão disco | `MENSAGENS/data/` | Fila antiban | Nenhuma (duplica possível) | Chip offline ignorado |
| **Resend** | API key env | `.env` | Nenhum | Nenhum | Raise / log |
| **Asaas webhook** | Header token | `.env` | Asaas reenvia | **Fraca** | 403/503 |
| **OpenRouteService** | API key env | `.env` | Nenhum | Cache viabilidade | Fallback OSRM |
| **Nominatim/ViaCEP** | Público | N/A | Cache | Hash geocoding | Timeout/log |
| **Sentry** | DSN | `.env` | SDK | N/A | Silent fail |

### Dependências críticas externas

1. **PostgreSQL** — sistema para sem ele
2. **Resend** (ou SMTP) — onboarding, tickets, ativação
3. **Node Alert Bridge** — módulo alertas inoperante sem ele
4. **Docker** (modo container OLT) — jobs OLT XL
5. **Redis** (recomendado) — rate limit, locks, sessões bridge em multi-worker

### Pontos frágeis de integração

- Token Telegram em trânsito para worker (HTTPS + HMAC mitigam, mas impacto alto)
- WhatsApp sessão em disco — backup/restore não padronizado
- OLT em Windows host — VPN via PowerShell/rasdial mais frágil que Linux
- Asaas — webhook-only; sem sync outbound evidente para criar assinaturas via API

---

## Operação diária

### Fluxo de login

```
Usuário → /rm/login/ ou /{slug}/login/
  → rate limit + lockout
  → authenticate (Argon2)
  → MFA? → /rm/mfa/verify/
  → must_change_password? → troca obrigatória
  → consent LGPD? → /consent-required/
  → dashboard (RM ou empresa)
```

### Onboarding nova ISP (manual)

1. RM cria empresa (`/rm/empresas/criar/`) — slug, plano, módulos, CNPJ
2. RM cria admin empresa ou envia e-mail ativação
3. Upload mapas CTO (se verificador)
4. Config alertas: token Telegram + linha WhatsApp + QR (se plano G/XL)
5. Config OLT + VPN (se plano XL)
6. Validar: `python manage.py onboarding_checklist --slug=...`

### Suporte (tickets)

- Cliente abre em `/{slug}/tickets/`
- RM responde em `/rm/tickets/`
- E-mails transacionais via Resend (criação, mensagens)
- Notificações in-app (`TicketNotification`)

### Rotinas automáticas (cron shell — não django-crontab)

| Script | Frequência sugerida | Função |
|--------|---------------------|--------|
| `scripts/cron-lgpd-delete.sh` | Diário 03:00 | DSR + purge tokens ativação |
| `scripts/cron-lgpd-retention.sh` | Diário 04:00 | Retenção LGPD |
| `scripts/cron-purge-caches.sh` | Semanal | Cache geocoding |
| `backup-db.sh` | Diário | Backup PostgreSQL |
| `check_bridge_health` | Contínuo/cron | Bridge stale → Sentry |

### O que quebra o sistema

| Falha | Sintoma | Severidade |
|-------|---------|------------|
| PostgreSQL down | 503 ready check | Total |
| `FIELD_ENCRYPTION_KEY` inválida | Erro ao carregar configs bridge/OLT | Alto |
| Bridge Node parado | Alertas não encaminham | Alto (módulo alertas) |
| Resend key inválida / modo teste | E-mails não chegam | Alto (onboarding) |
| Redis down (multi-worker) | Rate limit inconsistente, locks OLT | Médio |
| VPN OLT falha | Jobs OLT stuck/failed | Médio (módulo OLT) |
| Disco cheio (mapas/media) | Upload falha | Médio |

### Ações manuais recorrentes

- Pareamento WhatsApp (QR) após redeploy/restart bridge
- Re-save de campos criptografados após rotação de chave
- `deploy_vps.sh` após cada release
- Verificação Resend deliverability
- Monitoramento Sentry + logs em VPS

### Score operacional: **58 / 100**

Funcional para operação assistida (equipe RM), mas **não self-service** completo; muitos passos manuais e dependência de conhecimento técnico para workers e VPN.

---

## Frontend e operação

### Telas principais

| Área | Telas | Usuário |
|------|-------|---------|
| RM | Dashboard, empresas, usuários, mapas, tickets, relatórios, tenant usage | Admin RM |
| Empresa | Hub, painel, verificador (mapa), alertas, OLT, usuários, tickets | Admin/usuário ISP |
| Auth | Login RM/empresa, MFA, ativação conta, LGPD | Todos |
| Legal | Termos, políticas, FAQ, manual | Público |

### UX operacional

- **Server-rendered** — previsível, SEO irrelevante, bom para admin
- **Dark/light mode**, CSP nonce, loading global
- **Verificador** — Leaflet + APIs JSON; core do produto
- **Alertas** — depende de QR WhatsApp (UX frágil para cliente final)
- **OLT** — interface técnica; operador precisa entender VPN/serial ONU

### Pontos frágeis UX

1. Bridge offline — feedback pode ser tardio (`last_error`, health check)
2. E-mail “não enviado” — Resend test mode parece bug
3. Coluna ações usuários RM — select de templates e-mail (recém-adicionado) aumenta complexidade na tabela
4. PWA/service worker presente mas produto é B2B admin — valor limitado

---

## Dívida técnica

| Item | Prioridade | Esforço |
|------|------------|---------|
| Pins em `requirements.txt` | Alta | Baixo |
| Idempotência webhook Asaas | Alta | Médio |
| Guard production em `reset_superuser` | Alta | Baixo |
| Retry Resend | Média | Baixo |
| Celery/RQ para jobs OLT | Média | Alto |
| CD automatizado (staging/prod) | Média | Médio |
| Unificar workers Node (`MENSAGENS` vs `services/alert_bridge`) | Média | Médio |
| Teste de restore backup | Média | Baixo |
| Crispy forms em INSTALLED_APPS ou remover dep | Baixa | Baixo |
| API outbound Asaas completa | Baixa | Alto |

---

## O que está pronto

- [x] Multi-tenant funcional (core + middleware)
- [x] Verificador FTTH com cache e quotas
- [x] MFA + sessões enterprise
- [x] LGPD (consentimento, DSR, retenção, auditoria)
- [x] Módulo alertas Telegram→WhatsApp (com worker Node)
- [x] Módulo OLT/VPN (host + container)
- [x] Billing estrutura + webhook Asaas
- [x] Planos e enforcement de quotas
- [x] E-mail transacional (Resend + templates)
- [x] CI testes + security
- [x] Deploy VPS documentado
- [x] Criptografia campos sensíveis
- [x] Health checks e Sentry

---

## O que é perigoso

- [ ] Segredos históricos no Git (se não rotacionados)
- [ ] `reset_superuser` em produção
- [ ] `/health/security/` aberto
- [ ] Token Telegram em payload bridge
- [ ] Webhook Asaas sem dedup
- [ ] `FIELD_ENCRYPTION_KEY` incorreta / dados legados
- [ ] Mídia servida publicamente no Nginx (misconfig)
- [ ] Bridge/WhatsApp sem backup de sessão
- [ ] Deploy sem Redis em multi-worker Gunicorn

---

## O que precisa ser corrigido primeiro

**Ordem sugerida (impacto × risco operacional):**

| Prioridade | Ação | Motivo |
|------------|------|--------|
| P0 | Auditar Git por `.env` commitado; rotacionar segredos se confirmado | Vazamento total |
| P0 | Validar `FIELD_ENCRYPTION_KEY` + re-salvar configs afetadas | Bridge/OLT quebrados |
| P0 | Restringir health security + proteger `reset_superuser` | Superfície de ataque |
| P1 | Idempotência webhook Asaas | Integridade billing/tenant |
| P1 | Monitoramento bridge (systemd/cron) + runbook WhatsApp QR | Módulo alertas |
| P1 | Confirmar Redis em produção multi-worker | Locks e rate limit |
| P2 | Pins de dependências | Supply chain |
| P2 | Retry e-mail / dedup alertas | Confiabilidade |
| P2 | CD staging automatizado | Reduz erro humano deploy |

---

## Scores consolidados

| Dimensão | Score | Justificativa |
|----------|:-----:|---------------|
| **Técnico** | **72/100** | Arquitetura sólida, modular, testes e docs; gaps em async jobs e deps |
| **Operacional** | **58/100** | Manual-heavy, workers externos, cron shell, onboarding assistido |
| **Segurança** | **64/100** | Muitos controles; gestão segredos e superfícies públicas puxam nota |
| **Comercial** | **65/100** | Planos/quotas/billing estruturados; Asaas parcial, self-service limitado |

### Score composto readiness produção: **65 / 100**

**Interpretação:** sistema **apto para piloto controlado** com equipe técnica e clientes early-adopter; **não apto para escala comercial agressiva** sem fechar P0/P1 acima.

---

## Dependências sensíveis (referência rápida)

```
.env (local — NÃO commitar)
├── SECRET_KEY
├── DATABASE_URL
├── FIELD_ENCRYPTION_KEY          ← crítico para OLT, VPN, Telegram, CNPJ
├── RESEND_API_KEY
├── ALERT_BRIDGE_API_TOKEN
├── BRIDGE_HMAC_SECRET
├── ASAAS_WEBHOOK_TOKEN
├── REDIS_URL
├── SENTRY_DSN
└── OPENROUTESERVICE_API_KEY

Workers (fora do .env Django)
├── MENSAGENS/.env (TELEGRAM_BOT_TOKEN por empresa está no DB)
└── services/alert_bridge/.env (variante documentada)
```

---

## Próximos passos recomendados (decisão — não executar ainda)

1. **Validar ambiente produção/staging** contra checklist P0 deste documento
2. **Confirmar rotação de segredos** pós-auditoria Git
3. **Priorizar backlog** P0 → P1 com owner e janela de manutenção
4. **Rodar `onboarding_checklist`** em tenant real de referência
5. **Testar restore** de backup DB + documentar RTO/RPO
6. **Só então** implementar correções acordadas (segurança, tokens, deploy)

---

## Referências no repositório

| Documento | Caminho |
|-----------|---------|
| Documentação técnica | `docs/DOCUMENTACAO-TECNICA.md` |
| Auditoria segurança | `docs/security/AUDITORIA-SEGURANCA.md` |
| Pentest CASCAVEL | `docs/security/CASCAVEL_FINDINGS_REPORT.md` |
| Deploy VPS | `docs/deploy/DEPLOY.md` |
| Rotação segredos | `docs/deploy/ROTACAO_SECRETS.md` |
| OLT worker | `docs/deploy/OLT_WORKER.md` |
| Planos comerciais | `docs/PRECOS-RM-SYSTEMS.md`, `core/plans.py` |
| Env template | `.env.example` |

---

*Relatório gerado por análise estática do código e documentação existente. Nenhum teste destrutivo, alteração de código ou acesso a credenciais reais foi realizado nesta etapa.*
