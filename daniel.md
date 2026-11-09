# SaaS Verificador de Viabilidade — Contexto Completo

## 1. IDENTIDADE DO PROJETO

- **Nome**: SaaS Verificador de Viabilidade (RM Systems)
- **Propósito**: Plataforma multi-tenant para ISPs (Provedores de Internet) brasileiros que oferece:
  - **Verificador FTTH**: geolocalização + mapas de CTO + cálculo de viabilidade de instalação de fibra óptica
  - **Alertas**: bridge Telegram → WhatsApp para notificações de rede
  - **OLT Ops**: gerenciamento de OLTs (Terminais de Linha Óptica) Huawei/ZTE via SSH + execução de jobs
- **Público-alvo**: ISPs brasileiros de pequeno a médio porte
- **Idioma**: português (código, templates, mensagens, documentação)
- **Framework**: Django 5.2 (monolítico com API REST + SPA híbrido)
- **Banco**: PostgreSQL (Neon) via psycopg[binary] 3.2+
- **Cache**: Redis (opcional, fallback para local memory)
- **Worker externo**: Node.js para bridge Telegram→WhatsApp
- **Worker externo**: Docker para jobs OLT (rede isolada)
- **Monitoramento**: Sentry (sem PII, `send_default_pii=False`)

## 2. ESTRUTURA DE DIRETÓRIOS

```
/
├── saas_viabilidade/      # Config Django (settings, urls, wsgi, asgi, sentry, security_bootstrap)
├── core/                  # App principal (models, API, auth, MFA, LGPD, billing, middlewares, utils)
│   ├── billing/           # Integração Asaas (webhook)
│   ├── email/             # Backend Resend + envio transacional
│   ├── management/commands/  # 21 comandos de gestão
│   └── migrations/        # 26 migrations
├── ftth_viewer/           # App FTTH (geocoding, mapas KML/KMZ/CSV/XLS, viabilidade)
├── alerts/                # App Alertas (config WhatsApp, Telegram bridge)
├── olt_ops/               # App OLT (equipamentos, jobs SSH, fila)
├── frontend/              # SPA React + Vite + TypeScript + Tailwind
│   └── src/
│       ├── api/           # Axios client + endpoints (auth, account, admin, mfa, sessions)
│       ├── components/    # guards (roteamento), ui, auth, brand, dashboard, data, hub, layout
│       ├── contexts/      # AuthContext, ThemeContext
│       ├── layouts/       # AppShell, AuthLayout, MarketingLayout
│       ├── pages/         # 18 páginas (landing, login, dashboard, hub, perfil, etc.)
│       └── types/         # auth.ts, admin.ts
├── services/
│   ├── alert_bridge/      # Worker Node (Baileys WhatsApp + Telegraf Telegram)
│   └── olt_worker/        # Dockerfile + entrypoint (python manage.py olt_run_job)
├── templates/             # Django templates (17 subdiretórios: alerts, auth, company, core, docs, errors, includes, legal, rm, olt_ops)
├── static/                # CSS (design system v2), JS, imagens, vendor, well-known (BIMI)
├── scripts/               # 14 scripts: deploy, cron, segurança, túneis
├── docs/                  # 30 arquivos: LGPD, deploy, security, READINESS, UI redesign, BIMI
├── .github/workflows/     # tests.yml, security.yml
├── requirements.txt       # Dependências Python
├── .env.example           # 293 linhas de variáveis documentadas
├── gunicorn_config.py     # WSGI production
├── nginx.conf             # Reverse proxy + static/media
└── Makefile               # Comandos de atalho
```

## 3. ARQUITETURA DE SOFTWARE

### 3.1 Modelo Multi-tenant
- Empresas com slug único na URL: `/<company_slug>/<módulo>/...`
- Isolamento via middleware `SecureCompanyMiddleware` que valida:
  1. Usuário autenticado pertence à empresa do slug
  2. Se não pertencer: logout forçado + 403 Forbidden
  3. Se empresa inativa ou inexistente: 404
- RM admins (superusuários) têm acesso cross-tenant
- API REST filtra por `request.user.company` automaticamente nos serializers/viewsets

### 3.2 Hierarquia de Usuários
```
RM (is_staff=True, is_rm_admin=True)
├── Superusuário Django (is_superuser=True)
├── RM Admin  → acesso global, cross-tenant
│
└── COMPANY_ADMIN (role="COMPANY_ADMIN")
    ├── Gerencia usuários da empresa
    ├── Upload de mapas CTO
    ├── Configura alertas
    ├── Gerencia OLTs
    └── COMPANY_USER (role="COMPANY_USER")
        ├── Apenas consulta viabilidade
        ├── Visualiza mapas (read-only)
        └── Sem acesso a alertas/OLT
```

### 3.3 Módulos SaaS
```python
VERIFICADOR = {"code": "verificador", "name": "Verificador de Viabilidade", ...}
ALERTAS = {"code": "alertas", "name": "Alertas WhatsApp", ...}
OLT = {"code": "olt", "name": "Gerenciamento de OLTs", ...}
```
- Controlados por `Plan` (P=Essencial, M=Comercial, G=Operação, XL=Rede)
- Bloqueio via `SaasModuleMiddleware`
- Quotas impostas por `enforce_quota` (cache-based metering)

### 3.4 Planos
| Código | Nome | Verificador | Alertas | OLT | Users | Maps | CTOs | Viabilidades/mês |
|--------|------|-------------|---------|-----|-------|------|------|-------------------|
| P | Essencial | ✅ | ❌ | ❌ | 3 | 2 | 500 | 200 |
| M | Comercial | ✅ | ❌ | ❌ | 10 | 5 | 2000 | 1000 |
| G | Operação | ✅ | ✅ | ❌ | 25 | 20 | 10000 | 5000 |
| XL | Rede | ✅ | ✅ | ✅ | ∞ | ∞ | ∞ | ∞ |

### 3.5 Stack Tecnológica

#### Backend
- **Django 5.2** — framework principal
- **Django REST Framework** — API REST v1
- **djangorestframework-simplejwt 5.3** — JWT com claims customizadas (tenant, role, MFA)
- **drf-spectacular** — OpenAPI/Swagger
- **django-otp + pyotp** — MFA TOTP
- **cryptography (Fernet)** — criptografia de campos sensíveis
- **argon2-cffi** — hash de senha (Argon2)
- **paramiko** — SSH para OLTs Huawei/ZTE
- **gunicorn** — WSGI production (Linux)
- **whitenoise** — static files em produção
- **sentry-sdk** — error monitoring (sem PII)
- **resend** — e-mail transacional
- **django-cors-headers, django-crispy-forms, crispy-bootstrap5**
- **pandas, openpyxl, lxml, xlrd** — processamento de mapas (KML, KMZ, CSV, XLS, XLSX)

#### Frontend (SPA)
- **React 19** com **TypeScript 6.0**
- **Vite 8** — build tool + dev server
- **Tailwind CSS 4** — estilização
- **React Router v7** — roteamento SPA
- **TanStack React Query v5** — cache/estado servidor
- **Axios** — HTTP client com interceptors JWT + refresh automático
- **Framer Motion** — animações de transição
- **React Hook Form + Zod** — formulários com validação
- **Sonner** — toasts
- **Lucide React** — ícones
- **class-variance-authority + tailwind-merge** — utility CSS

#### Infrastructure
- **PostgreSQL** (via Neon ou local)
- **Redis** (cache, rate limit, lockout, MFA remember, bridge nonce)
- **Nginx** — reverse proxy + static files + SSL
- **Docker** — worker OLT isolado por job
- **Node.js 18+** — alert bridge (Baileys WhatsApp + Telegraf)
- **GitHub Actions** — CI (testes + segurança + SAST)

## 4. CORE (APP PRINCIPAL)

### 4.1 Models (core/models.py — 42000+ chars)

#### Company
- `name`, `slug` (unique), `cnpj` (raw, hashed em `cnpj_hash`)
- `plan_code` (P/M/G/XL), `modules` (JSON array de códigos)
- `is_active`, `billing_status` (active/suspended/trial)
- `address`, `phone`, `email`, `logo`
- Métodos: `has_module(code)`, `get_plan()`, `get_active_modules()`
- Signals: `pre_save` → gera `cnpj_hash` (SHA-256 + salt), `slug` automático

#### CustomUser (AbstractUser)
- `company` (FK → Company, nullable para RM admins)
- `role` (RM/COMPANY_ADMIN/COMPANY_USER/STAFF)
- `phone`, `must_change_password`
- `cnpj_hash` opcional (auto-preenchido se tiver company)
- Properties: `is_rm_admin`, `is_company_admin`, `is_company_user`
- MFA fields: `mfa_secret`, `mfa_enabled`, `mfa_backup_codes` (criptografado), `mfa_verified_at`

#### CTOMapFile
- `company` (FK), `uploaded_by` (FK)
- `file` (FileField), `file_name`, `file_type`, `file_size`
- `description`, `uploaded_at`, `updated_at`
- `parsed_data` (JSON → pontos CTO)
- Cada arquivo representa um mapa (KML/KMZ/CSV/XLS) com pontos CTO

#### Ticket + TicketMessage + TicketNotification
- Sistema de suporte interno (empresa → RM)
- Ticket: `company`, `user`, `subject`, `status` (open/closed/archived), `priority`
- TicketMessage: `ticket`, `author`, `content`, `created_at`
- TicketNotification: `ticket`, `recipient`, `read_at`

#### LGPD
- `ConsentRecord`: `user`, `document_type`, `document_version`, `accepted_at`, `ip_address`, `user_agent`
- `DataSubjectRequest`: `user`, `request_type` (export/delete/rectify), `status`, `details`
- `LgpdExportDownload`: `user`, `token_hash`, `expires_at`, `download_count`, `max_downloads`

#### Security
- `AccountActivationToken`: `user`, `token_digest` (SHA-256), `django_token`, `created_at`, `expires_at`, `used_at`, `created_ip`
- `SecurityAuditEvent`: `user`, `event_type`, `severity`, `description`, `ip_address`, `user_agent`, `metadata` (JSON)
- `UserSessionRecord`: `user`, `session_key`, `access_token_hash`, `ip_address`, `user_agent`, `last_seen`, `expires_at`

#### CompanyBilling
- `company` (OneToOne), `asaas_customer_id`, `asaas_subscription_id`
- `plan_code`, `status`, `current_period_start`, `current_period_end`
- `last_webhook_at`, `last_webhook_event`
- Métodos: `apply_payment_received()`, `apply_payment_overdue()`, `apply_subscription_cancelled()`

### 4.2 Configuração Django (saas_viabilidade/settings.py — 652 linhas)

#### Security Bootstrap (security_bootstrap.py)
Executado ANTES de qualquer config sensível:
1. Detecta ambiente (VPS/dev/test) via `VPS_ENVIRONMENT` ou `/etc/nginx`
2. Valida `SECRET_KEY` (≥50 chars, não conhecida, sem prefixo `django-insecure-`)
3. Valida `FIELD_ENCRYPTION_KEY` (chave Fernet válida, ≥44 chars)
4. `DEBUG=False` forçado em produção (VPS + DEBUG=True → `SecurityBootstrapError`)
5. `SERVE_MEDIA_VIA_DJANGO` proibido em produção
6. Configura HTTPS, CSRF HttpOnly, Session/Cookie Secure

#### Middleware Chain (13 middlewares, ordem crítica):
1. `SecurityMiddleware` — Django security
2. `WhiteNoiseMiddleware` — static files
3. `RequestIdMiddleware` — X-Request-ID header
4. `CspNonceMiddleware` — CSP nonce por request
5. `SessionMiddleware` — Django sessions
6. `DevTunnelCsrfMiddleware` — CSRF compatível com túneis (ngrok/Cloudflare)
7. `CorsMiddleware` — CORS headers
8. `CommonMiddleware` — Django common
9. `CrlfProtectionMiddleware` — CRLF injection
10. `HttpMethodRestrictionMiddleware` — bloqueia TRACE/CONNECT + custom
11. `CsrfViewMiddleware` — Django CSRF
12. `AuthenticationMiddleware` — Django auth
13. `OTPMiddleware` — django-otp
14. `MfaEnforcementMiddleware` — força MFA verificado
15. `SessionIdleTimeoutMiddleware` — timeout de inatividade (30min)
16. `SessionRegistryMiddleware` — valida sessão ativa + IP bind + expiração
17. `PasswordChangeMiddleware` — força troca de senha no 1º acesso
18. `ConsentMiddleware` — exige aceite LGPD
19. `SecureCompanyMiddleware` — isolamento multi-tenant
20. `SaasModuleMiddleware` — bloqueia módulos não contratados
21. `FrontendSpaRedirectMiddleware` — SSR→SPA redirect
22. `UiV2PreviewMiddleware` — UI v2 preview via cookie
23. `GlobalRateLimitMiddleware` — rate limit global
24. `SecurityHeadersMiddleware` — CSP, HSTS, X-Frame-Options, etc.
25. `MessageMiddleware` — Django messages
26. `XFrameOptionsMiddleware` — clickjacking

#### Apps Instalados
```
saas_viabilidade (custom runserver), django.contrib.admin, auth, contenttypes, sessions, messages, staticfiles,
django_otp, django_otp.plugins.otp_totp, django_otp.plugins.otp_static,
corsheaders, rest_framework, rest_framework_simplejwt (token_blacklist),
drf_spectacular, core, ftth_viewer, alerts, olt_ops
```

#### Password Validators
- Mínimo 14 caracteres
- Argon2 (hasher primário)
- Similarity, Common, Numeric validators

#### Conexão Banco
- `DATABASE_URL` obrigatória
- PostgreSQL com SSL obrigatório se remoto
- `connect_timeout=10`
- `conn_max_age` configurável

### 4.3 API REST (core/api.py + core/api_urls.py)

Endpoints registrados via `DefaultRouter` + ViewSets:

```
GET    /api/v1/companies/           → CompanyViewSet (list, retrieve, stats)
POST   /api/v1/companies/           → RM only
PATCH  /api/v1/companies/{id}/      → Company admin or RM
GET    /api/v1/companies/{id}/stats/ → CompanyStatsView
GET    /api/v1/users/               → UserViewSet (list, create, retrieve, update)
POST   /api/v1/users/               → Company admin cria COMPANY_USER
GET    /api/v1/maps/                → CTOMapFileViewSet (list, retrieve, upload)
POST   /api/v1/maps/                → Upload de arquivo
POST   /api/v1/auth/login/          → LoginView (username/email + password)
POST   /api/v1/auth/refresh/        → RefreshTokenView
POST   /api/v1/auth/logout/         → LogoutView (blacklist refresh)
GET    /api/v1/auth/me/             → MeView (user + company + permissions)
POST   /api/v1/auth/change-password/ → ChangePasswordView
GET    /api/v1/auth/mfa/status/     → MFAStatusView
POST   /api/v1/auth/mfa/setup/      → MFASetupView (gera secret + QR)
POST   /api/v1/auth/mfa/verify/     → MFAVerifyView (valida TOTP)
POST   /api/v1/auth/mfa/disable/    → MFADisableView
GET    /api/v1/auth/sessions/       → SessionListView
DELETE /api/v1/auth/sessions/{id}/  → SessionRevokeView
GET    /api/v1/billing/             → BillingStatusView
GET    /api/v1/billing/portal/      → BillingPortalView (redirect Asaas)
GET    /api/v1/schema/              → SchemaView (Swagger/OpenAPI)
```

#### Autenticação API
- JWT (access 15min, refresh 7d, rotate refresh)
- Custom token com claims: `tenant_slug`, `role`, `company_id`, `mfa_verified`
- Refresh automático no frontend (Axios interceptor)
- MFA pode ser exigido via settings (`MFA_REQUIRED`)
- Rate limiting: burst 60/min, sustained 2000/hour (DRF throttling)

### 4.4 Controle de Acesso (core/permissions.py)
- `IsRmViaApiKeyOrAuthenticated` — API Key RM ou JWT
- `IsCompanyAdminOrRm` — COMPANY_ADMIN ou RM
- `IsCompanyUserOrAdmin` — COMPANY_USER (read-only) ou COMPANY_ADMIN
- `IsRM` — apenas RM
- `IsAuthenticatedAndMfaVerified` — JWT + MFA verificado na sessão
- Todas as viewsets usam `DjangoModelPermissions` + permissões customizadas

### 4.5 MFA (core/mfa_service.py + core/mfa_lockout.py)
- TOTP (Time-based One-Time Password) via pyotp
- Geração de QR code (qrcode[pil])
- Backup codes: 8 códigos de emergência, uso único
- Trusted devices: cookie por 30 dias
- Lockout após 5 tentativas inválidas (15 min)
- `mfa_required_for(user)`: RM ou COMPANY_ADMIN (configurável)
- Verificação: comparar TOTP + validar backup codes
- Middleware `MfaEnforcementMiddleware` redirect para `/rm/mfa/`

### 4.6 Sessões Enterprise (core/session_security.py + core/session_lockout.py)
- `UserSessionRecord` no banco (não apenas session backend)
- `_access_token`: token de 32 bytes armazenado na sessão + hash no banco
- Bind de IP: se IP mudar durante sessão → logout
- Concorrência máxima: `SESSION_MAX_CONCURRENT` (padrão 3)
- Revogação no login: `SESSION_REVOKE_ON_NEW_LOGIN` revoga sessões anteriores
- Idle timeout: 30 min (configurável)
- Lockout de sessão: 10 falhas → bloqueio 15 min
- Tabela `UserSessionRecord` com `session_key`, `access_token_hash`, `ip_address`, `last_seen`, `expires_at`
- Touch a cada request (`SessionRegistryMiddleware`)

### 4.7 LGPD (vários arquivos: lgpd_views.py, lgpd_constants.py, lgpd_export.py)
- Consentimento obrigatório: Termos de Uso + Política de Privacidade + Cookies
- Versão dos documentos: `LEGAL_DOCUMENT_VERSION` (2026-05-21)
- Portal do titular: `meus-dados/` — exportar (JSON/CSV), excluir, retificar
- Export assinado: token HMAC, ZIP criptografado, TTL 24h, máx 5 downloads
- DSR (Data Subject Request) automatizado via `process_data_subject_requests` command
- Encarregado (DPO): `privacidade@rmsys.com.br`
- Retenção: consentimento 5 anos, auditoria 1 ano, tickets 2 anos, tokens 7 dias
- Cache de geocoding: apenas hash SHA-256 do endereço (sem endereço completo)
- CNPJ: apenas `cnpj_masked` na API (últimos 2 dígitos), busca via `cnpj_hash`

### 4.8 Criptografia (core/field_encryption.py + core/encrypted_fields.py)
- `EncryptedField` baseado em Fernet (simétrico)
- Campos criptografados: `mfa_secret`, `mfa_backup_codes`, senhas OLT, tokens Telegram
- `FIELD_ENCRYPTION_KEY` obrigatória (≥44 chars, url-safe base64)
- Fallback em dev: derivação de SECRET_KEY (só com `ALLOW_FIELD_ENCRYPTION_SECRET_FALLBACK=true`)
- Chave validada no bootstrap (formato Fernet válido)

### 4.9 CNPJ (core/cnpj_utils.py)
- `cnpj_hash(cnpj_raw)`: SHA-256(CNPJ + salt) → hex
- `cnpj_masked(cnpj_raw)`: `**********99` (apenas últimos 2 dígitos)
- Salt: `CNPJ_HASH_SALT` do .env ou derivado de SECRET_KEY
- Busca de empresa por CNPJ: apenas por hash (nunca raw)

### 4.10 Rate Limiting (core/rate_limiting.py + core/middleware_rate_limit_global.py)
- `GlobalRateLimitMiddleware`: token bucket por IP, 100 req/min (configurável), 503 após esgotar
- `FORCE_RATE_LIMIT` para ativar em DEBUG
- DRF throttling: `AnonRateThrottle` + `UserRateThrottle` + `ScopedRateThrottle`
- Burst: 60/min, Sustained: 2000/hour
- Cache: Redis (preferencial) ou local memory

### 4.11 Auditoria (core/audit_trail.py + core/audit_logger.py + core/log_sanitizer.py)
- `SecurityAuditEvent`: evento de segurança persistente no banco
- `record_security_event(user, event_type, severity, description, ...)`
- Event types: login, login_failed, mfa_verified, consent_given, data_exported, etc.
- Audit logger: JSON estruturado para ferramentas externas
- Sanitizer: remove dados sensíveis (senhas, tokens, IPs completos) dos logs
- `operational_sanitizer.py`: sanitiza logs OLT (remove senhas de equipamento)

### 4.12 Billing (core/billing/asaas_webhook.py)
- Integração com Asaas (gateway de pagamento brasileiro)
- Webhook assinado via `asaas-access-token` ou `X-Asaas-Token`
- Eventos tratados:
  - `PAYMENT_RECEIVED`, `PAYMENT_CONFIRMED`, `PAYMENT_RECEIVED_IN_CASH` → ativa empresa
  - `PAYMENT_OVERDUE`, `PAYMENT_DELETED` → suspende
  - `SUBSCRIPTION_DELETED`, `SUBSCRIPTION_INACTIVATED` → cancela
- Mapeia `asaas_customer_id` e `asaas_subscription_id` → `CompanyBilling`
- Rota: `POST /api/webhooks/asaas/`

### 4.13 Email (core/email/resend_backend.py + core/email_branding.py)
- Backend customizado Resend (transacional)
- Branding: logo, letreiro, cor, banner nos e-mails
- Templates HTML com imagem embedada (base64)
- Envio de: ativação de conta, reset de senha, notificações de ticket
- Fallback: SMTP (legado)

### 4.14 JWT Custom (core/jwt_tokens.py)
- `CustomAccessToken` e `CustomRefreshToken`
- Claims adicionais:
  - `tenant_slug`: slug da empresa (ou "rm" para admins)
  - `role`: papel do usuário
  - `company_id`: ID da empresa
  - `mfa_verified`: bool (verificado no momento do login)
- Refresh token blacklist via `rest_framework_simplejwt.token_blacklist`

### 4.15 Management Commands (21 comandos)

| Comando | Função |
|---------|--------|
| `check_deploy` | Valida configuração de deploy |
| `check_security` | Auditoria de segurança (SECRET_KEY, encrypt, CSP, HSTS) |
| `clear_rate_limit` | Zera rate limit de um IP |
| `clear_tickets` | Limpa/Age tickets antigos |
| `debug_login` | Debug de fluxo de login |
| `lgpd_compliance_report` | Relatório de compliance LGPD |
| `lgpd_data_inventory` | Inventário de dados pessoais |
| `normalize_superusers` | Normaliza superusuários |
| `onboarding_checklist` | Checklist de onboarding |
| `process_data_subject_requests` | Processa DSRs pendentes |
| `purge_activation_tokens` | Limpa tokens de ativação expirados |
| `purge_lgpd_retention` | Limpa dados fora do prazo de retenção |
| `purge_old_caches` | Limpa caches antigos |
| `reset_superuser` | Reseta senha de superusuário |
| `rotate_bridge_credentials` | Rotaciona credenciais do bridge |
| `scan_security` | Scan de segurança no código |
| `setup_p1_security` | Configura segurança fase 1 (SECRET_KEY, FIELD_ENCRYPTION_KEY) |
| `setup_p2_lgpd` | Configura LGPD fase 2 |
| `setup_p3_security` | Configura segurança avançada fase 3 |
| `test_resend_email` | Testa envio de e-mail via Resend |

## 5. FTTH VIEWER (APP)

### 5.1 Models
- `ViabilidadeCache`: `lat`, `lon`, `company`, `mapas_hash`, `resultado` (JSON), `created_at`, `expires_at`
- `GeocodingCache`: `query_hash` (SHA-256 do endereço), `lat`, `lng`, `resultado` (JSON), `expires_at`
  - **LGPD**: apenas hash do endereço armazenado, não o endereço completo

### 5.2 Views (ftth_viewer/views.py — 1057 linhas)
- `index()`: página principal do FTTH Viewer
- `api_arquivos()`: lista mapas disponíveis (do banco, SEMPRE filtrado por empresa)
- `api_coordenadas()`: retorna coordenadas de um mapa (KML/KMZ/CSV/XLS)
- `api_contar_pontos()`: conta CTOs em um arquivo
- `api_geocode()`: geocodificação Nominatim (OSM) + cache
- `api_cep()`: consulta CEP (ViaCEP → fallback BrasilAPI)
- `api_geocode_suggestions()`: autocomplete de endereços
- `api_verificar_viabilidade()`:
  1. Filtrar CTOs por distância euclidiana (5km raio)
  2. Calcular rota real (thread pool paralelo)
  3. Classificar viabilidade (viável ≤300m, limitada ≤800m, inviável >800m)
  4. Cache por empresa + hash de mapas ativos
- `api_adicionar_cto()`: adiciona CTO a mapa existente
- `api_remover_cto()`: remove CTO de mapa
- `api_cache_geocoding_stats()`: estatísticas do cache (RM only)
- `api_cache_geocoding_clear()`: limpa cache (RM only)

### 5.3 Utils (ftth_viewer/utils.py)
- Parsing: `ler_kml()`, `ler_kmz()`, `ler_csv()`, `ler_excel()`
- Geocoding: `get_cached_geocoding()`, `set_cached_geocoding()` com hash SHA-256
- Distância: `calcular_distancia()` (Haversine), `calcular_rota_ruas_single()` (OpenRouteService)
- Classificação: `classificar_viabilidade(distancia)` → "viável" | "limitada" | "inviável"
- `normalize_address()`: normaliza endereço para busca
- `generate_search_variations()`: gera variações da busca para encontrar endereços
- `get_all_ctos(company)`: carrega todos os CTOs de uma empresa
- `adicionar_cto_ao_mapa()` / `remover_cto_do_mapa()`: manipula KML/KMZ diretamente
- `invalidate_ftth_map_caches()`: invalida caches ao modificar mapas
- `filtrar_coordenadas_brasil()`: filtra coordenadas dentro do território brasileiro

### 5.4 URLs
```
/verificador/                          → index
/verificador/api/arquivos              → api_arquivos
/verificador/api/coordenadas           → api_coordenadas
/verificador/api/contar-pontos         → api_contar_pontos
/verificador/api/geocode               → api_geocode
/verificador/api/geocode-suggestions   → api_geocode_suggestions
/verificador/api/cep                   → api_cep
/verificador/api/verificar-viabilidade → api_verificar_viabilidade
/verificador/api/cto/adicionar         → api_adicionar_cto
/verificador/api/cto/remover           → api_remover_cto
/verificador/api/cache/stats           → api_cache_geocoding_stats
/verificador/api/cache/limpar          → api_cache_geocoding_clear
```

## 6. ALERTAS (APP)

### 6.1 Models (alerts/models.py — 10000+ chars)
- `AlertBridgeConfig`: configuração por empresa
  - `company` (OneToOne), `is_active`, `telegram_token` (criptografado), `telegram_group_id`
  - `whatsapp_group_jid` (criptografado), `filter_enabled`, `filter_rules` (JSON), `filter_match_all`
  - `updated_at`, `last_webhook_at`
- `WhatsAppLine`: linha WhatsApp ativa
  - `company` (FK), `phone`, `is_active`, `connection_status`
  - `qrcode_data` (criptografado), `last_qr_at`, `connected_at`

### 6.2 Views
- `settings()`: painel de configuração de alertas
- `worker_configs_api()`: API interna para o bridge Node.js (autenticada via HMAC)
- `whatsapp_qr_api()`: retorna QR code para pareamento WhatsApp
- `whatsapp_status_api()`: status da conexão WhatsApp

### 6.3 URLs
```
/<company_slug>/alertas/config/       → settings
/api/internal/alert-bridge/configs/   → worker_configs_api
/<company_slug>/alertas/api/qr        → whatsapp_qr_api
/<company_slug>/alertas/api/status    → whatsapp_status_api
```

## 7. OLT OPS (APP)

### 7.1 Models (olt_ops/models.py — 8600+ chars)
- `OltEquipment`: equipamento OLT
  - `company` (FK), `name`, `ip_address`, `ssh_port` (padrão 22)
  - `ssh_username`, `ssh_password` (criptografado), `model` (huawei/zte)
  - `vpn_required`, `vpn_config` (criptografado)
- `OltJob`: job de operação
  - `company` (FK), `equipment` (FK), `operation` (list_onts/delete_ont)
  - `parameters` (JSON), `status` (pending/running/completed/failed)
  - `started_at`, `completed_at`, `error_log`
  - `created_by` (FK)
- `OltJobResult`: resultado do job
  - `job` (FK), `output_sanitized` (log sem dados sensíveis)
  - `parsed_data` (JSON), `duration_ms`

### 7.2 Services
- `huawei_cli.py`: comandos SSH para OLT Huawei
- `zte_cli.py`: comandos SSH para OLT ZTE
- `job_runner.py`: executa job (thread local ou container Docker)
- `queue.py`: fila FIFO de jobs (máx paralelo configurável)

### 7.3 Segurança OLT
- Senhas criptografadas via Fernet (`EncryptedField`)
- `OLT_LOG_MAX_CHARS`: 200000 chars máx no log
- `OLT_LOG_RETENTION_DAYS`: 7 dias
- Logs sanitizados (sem senhas, IPs completos)
- VPN por job: suporte a OpenVPN/L2TP/strongSwan (config via docker)
- Dois modos de execução:
  - `host` (padrão): thread no Gunicorn + mutex VPN global
  - `container`: Docker por job (rede isolada, timeout 1h)

## 8. FRONTEND (SPA)

### 8.1 Estrutura de Rotas (App.tsx)
```
/                                           → LandingPage (MarketingLayout)
/rm/login                                   → RmLoginPage (AuthLayout, GuestRoute)
/rm/password-reset                          → PasswordResetPage
/rm/password-reset/confirm                  → PasswordResetConfirmPage
/rm/dashboard                               → RmDashboardPage (ProtectedRoute + RmRoute)
/rm/empresas                                → RmCompaniesPage
/rm/usuarios                                → RmUsersPage
/rm/mapas                                   → RmMapsPage
/rm/billing                                 → BillingStubPage
/rm/perfil                                  → ProfilePage
/<slug>/login                               → CompanyLoginPage (GuestRoute)
/<slug>/password-reset                      → PasswordResetPage
/<slug>/password-reset/confirm              → PasswordResetConfirmPage
/<slug>/hub                                 → CompanyHubPage (ProtectedRoute + TenantRoute)
/<slug>/dashboard                           → CompanyDashboardPage
/<slug>/usuarios                            → CompanyUsersPage
/<slug>/mapas                               → CompanyMapsPage
/<slug>/billing                             → BillingStubPage
/<slug>/perfil                              → ProfilePage
/ativar-conta/:token                        → ActivatePage
/mfa                                        → MfaPage (MfaGuard)
/mfa/setup                                  → MfaSetupPage (MfaSetupGuard)
/change-password                            → ChangePasswordPage (TokenRoute)
/consent-required                           → SsrRedirectPage
```

### 8.2 Guards (components/guards.tsx)
- `GuestRoute`: se autenticado → redirect para dashboard
- `ProtectedRoute`: exige token + user + mfa_verified
- `MfaGuard`: exige mfa_pending_token
- `MfaSetupGuard`: exige que MFA seja necessário mas não configurado
- `TenantRoute`: valida slug da empresa no token JWT
- `RmRoute`: apenas role=RM
- `TokenRoute`: apenas token presente

### 8.3 Auth Flow (contexts/auth-context.tsx)
- `AuthProvider` com estado global de autenticação
- Query `['me']` via TanStack Query (fetch /api/v1/auth/me/)
- `applyLoginResult()`: processa resposta de login (MFA, change password, redirect)
- `logout()`: chama API + limpa storage + query cache
- `refreshUser()`: invalida query `['me']`
- `authStorage`: localStorage wrapper (access, refresh, mfa_pending)

### 8.4 API Client (api/client.ts)
- Axios instance com baseURL `/api/v1`
- Interceptor request: adiciona `Authorization: Bearer <token>`
- Interceptor response: refresh automático em 401 (com retry)
- `refreshAccessToken()`: POST /api/v1/auth/refresh/ + atualiza storage

### 8.5 Features do Frontend
- Tema escuro/claro (prefers-color-scheme + localStorage)
- Animações com Framer Motion (AnimatePresence)
- Toasts com Sonner
- React Hook Form + Zod para formulários
- TanStack Query para cache de API (staleTime 30s, retry 1)
- Lazy loading de componentes (aguardando code-splitting)

## 9. WORKERS EXTERNOS

### 9.1 Alert Bridge (services/alert_bridge/)
- **Linguagem**: Node.js (v18+)
- **Framework**: Telegraf (Telegram) + Baileys (WhatsApp)
- **Função**: Bridge multi-tenant: recebe mensagens do Telegram e encaminha para grupos WhatsApp
- **Autenticação**: HMAC SHA-256 (headers: X-Bridge-Token, X-Bridge-Timestamp, X-Bridge-Nonce, X-Bridge-Signature)
- **Config**: carregada via API REST (`/api/internal/alert-bridge/configs/`)
- **Filtros**: por palavra-chave (include), match all/any
- **Anti-replay**: timestamp ±120s, nonce TTL 300s (Redis)
- **Arquivos**:
  - `src/bridge-auth.js`: geração de headers HMAC
  - `src/filters.js`: lógica de filtro de mensagens
  - `src/load-configs.js`: carrega configs da API Django
  - `src/index.js` (via MENSAGENS/): loop principal

### 9.2 OLT Worker (services/olt_worker/)
- **Linguagem**: Python (mesmo código Django)
- **Imagem**: `python:3.12-slim-bookworm` + OpenVPN + strongSwan + xl2tpd
- **Entrypoint**: `python manage.py olt_run_job --job-id N --operation list|delete`
- **Rede**: container Docker com VPN isolada por job
- **Build**: `scripts/build-olt-worker.sh`

## 10. SEGURANÇA

### 10.1 TLS/SSL
- HTTPS obrigatório em produção (via Nginx + Let's Encrypt/Certbot)
- `SECURE_SSL_REDIRECT=True` na VPS
- `SESSION_COOKIE_SECURE=True` em produção
- `CSRF_COOKIE_SECURE=True` em produção
- `CSRF_COOKIE_HTTPONLY=True` em produção
- HSTS configurável via `SECURE_HSTS_SECONDS`

### 10.2 Content Security Policy (CSP)
- Modo strict-dynamic (nonce + hashes, sem unsafe-inline em scripts)
- `CspNonceMiddleware`: gera nonce de 16 bytes por request
- `SecurityHeadersMiddleware`: aplica headers CSP em todas as respostas
- `CSP_STRICT` configurável
- Hosts img-src e connect-src configuráveis
- Style-src: nonce + CDN Bootstrap + Font Awesome

### 10.3 Proteções HTTP
- CRLF injection: `CrlfProtectionMiddleware`
- Métodos HTTP: bloqueia TRACE, CONNECT + custom (`HttpMethodRestrictionMiddleware`)
- Server header removido: `wsgi_security.strip_server_header_wsgi`
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- Referrer-Policy: strict-origin-when-cross-origin

### 10.4 Rate Limiting
- Global: token bucket por IP (100 req/min)
- DRF: burst 60/min, sustained 2000/hour
- Login: rate limit por IP + username (evita enumeração)
- Lockout login: 5 falhas → 15 min bloqueio
- Lockout MFA: 5 tentativas inválidas → 15 min
- Lockout sessão: 10 falhas → 15 min
- Tudo configuravel via settings

### 10.5 Proteção de Dados
- CNPJ: apenas masked + hash (nunca raw na API)
- Senhas: Argon2 (nunca plaintext)
- Chaves secretas: Fernet encryption (FIELD_ENCRYPTION_KEY)
- Tokens de ativação: SHA-256 hash no banco (nunca plaintext)
- Tokens de sessão: SHA-256 hash no banco
- Geocoding: apenas hash SHA-256 do endereço
- Logs sanitizados: sem PII, senhas, tokens
- Sentry: `send_default_pii=False`

### 10.6 Monitoramento
- Sentry: error tracking (sem PII), traces configuráveis
- Health endpoints:
  - `/health/` → liveness
  - `/ready/` → readiness (DB + SECRET_KEY + debug check)
  - `/health/security/` → flags de segurança (IP restrito)
  - `/sentry-debug/` → erro de teste (só DEBUG)

## 11. INFRAESTRUTURA

### 11.1 Produção (VPS Hostinger)
- **Servidor**: Gunicorn (workers = CPU*2+1, sync, preload)
- **Proxy**: Nginx (reverse proxy + SSL + gzip + serve static)
- **Static**: WhiteNoise + Nginx alias (expires 1y, immutable)
- **Media**: Django protegido (signed URLs ou auth check)
- **Logs**: `/var/log/gunicorn/`, `/var/log/nginx/saas-viabilidade-*`
- **Banco**: PostgreSQL (Neon) com SSL
- **Cache**: Redis (opcional)
- **Monitoramento**: Sentry

### 11.2 Desenvolvimento
- `manage.py runserver` customizado (sobe MENSAGENS bridge junto)
- SQLite ou PostgreSQL local
- Túneis: ngrok, Cloudflare Tunnel, localtunnel (scripts dev-tunnel.ps1)
- Vite dev server em 5173 com proxy Django
- `.env.local` para override pessoal

### 11.3 CI/CD (GitHub Actions)
- **tests.yml**: Python 3.12, migrate, test específicos (core, olt_ops, saas_viabilidade)
  - Roda em push/PR para main/master/develop
  - SQLite para CI, FIELD_ENCRYPTION_KEY fixa
- **security.yml**: `check --deploy`, `check_security`, pip-audit, Bandit SAST, scripts/security-check.sh
  - Roda semanal (cron) + push/PR

### 11.4 Scripts de Deploy/Manutenção
- `run-cascavel-staging.ps1`: deploy staging
- `security-audit.sh`: auditoria de segurança
- `security-check.sh`: scan de secrets no repositório
- `cron-lgpd-delete.sh`: processa exclusão LGPD
- `cron-lgpd-retention.sh`: limpa retenção LGPD
- `cron-purge-caches.sh`: limpa caches
- `build-olt-worker.sh`: build Docker OLT worker
- `generate_bimi_logo.py`: gera logo BIMI
- `upload_bimi_logo_vps.sh`: upload BIMI para VPS
- `dev-ngrok.ps1` / `dev-tunnel.ps1`: túneis de desenvolvimento
- `download-vendor-static.ps1`: baixa dependências JS/CSS vendor

## 12. DEPENDÊNCIAS PRINCIPAIS

### Python (requirements.txt — 46 linhas)
```
Django, python-dotenv, cryptography>=42.0.0,
django-otp, pyotp, qrcode[pil], argon2-cffi,
djangorestframework, djangorestframework-simplejwt>=5.3.0,
django-cors-headers, django-crispy-forms, crispy-bootstrap5, Pillow,
pandas, openpyxl, requests, lxml, xlrd,
django-redis, dj-database-url, psycopg[binary]>=3.2.10,
gunicorn, waitress, whitenoise, paramiko,
sentry-sdk, resend, drf-spectacular
```

### Node (frontend/package.json)
```
React 19, React Router 7, TanStack Query 5, Axios, Framer Motion 12,
React Hook Form 7 + Zod 4, Sonner 2, Tailwind CSS 4,
Vite 8, TypeScript 6, ESLint 10, Lucide React
```

### Node (services/alert_bridge/package.json)
```
@whiskeysockets/baileys (WhatsApp), telegraf (Telegram),
pino (logging), qrcode-terminal, dotenv
```

## 13. TESTES

### Estrutura
- Testes Django (TestCase + APITestCase)
- Arquivos:
  - `core/tests.py`: modelos, API, health endpoints
  - `core/tests_activation.py`: fluxo completo de ativação
  - `core/tests_api_tenant.py`: isolamento multi-tenant RBAC
  - `core/tests_quotas.py`: enforce_quota (não lido)
  - `olt_ops/tests_vpn_slot.py`: slots VPN (não lido)
  - `olt_ops/tests_dispatcher.py`: dispatcher de jobs (não lido)
  - `saas_viabilidade/tests_sentry_bootstrap.py`: bootstrap Sentry (não lido)
- Helpers: `core/test_helpers.py` (`make_company()`, `api_force_login()`)

### Cobertura (CI)
- `python manage.py test core.tests_quotas core.tests_api_tenant olt_ops.tests_vpn_slot olt_ops.tests_dispatcher saas_viabilidade.tests_sentry_bootstrap`

## 14. VARIÁVEIS DE AMBIENTE (.env.example — 293 linhas)

### Críticas (OBRIGATÓRIAS)
- `SECRET_KEY` — ≥50 chars, alta entropia, sem prefixo django-insecure-
- `DATABASE_URL` — PostgreSQL connection string
- `FIELD_ENCRYPTION_KEY` — chave Fernet url-safe base64

### Importantes
- `DEBUG` — False em produção (boot falha se DEBUG=True na VPS)
- `ALLOWED_HOSTS` — domínios separados por vírgula
- `CORS_ALLOWED_ORIGINS` — origens CORS
- `CSRF_TRUSTED_ORIGINS` — origens CSRF confiáveis
- `RESEND_API_KEY` — chave da API Resend
- `ASAAS_WEBHOOK_TOKEN` — token de autenticação do webhook Asaas
- `SENTRY_DSN` — DSN do Sentry

### Segurança
- `CNPJ_HASH_SALT` — salt para hash de CNPJ
- `GEOCODING_CACHE_SALT` — salt para hash de geocoding
- `BRIDGE_HMAC_SECRET` — segredo HMAC do alert bridge
- `CSP_STRICT` — CSP strict-dynamic
- `MFA_REQUIRED` — exigir MFA
- `SESSION_BIND_IP` — bind de IP na sessão

### Configuração
- `FRONTEND_MODE` — hybrid/spa/ssr
- `FRONTEND_URL` — URL do Vite dev server
- `REDIS_URL` — conexão Redis
- `OLT_EXECUTION_MODE` — host/container
- `VIABILIDADE_VIABLE` / `VIABILIDADE_LIMITADA` / `VIABILIDADE_INVIAVEL` — distâncias em metros

## 15. DOCUMENTAÇÃO (docs/)

| Arquivo | Conteúdo |
|---------|----------|
| `DEPLOY/` | Guia de deploy completo |
| `DESIGN_SYSTEM.md` | Design system v2 |
| `DOCUMENTACAO-TECNICA.md` | Documentação técnica geral |
| `FRONTEND_REFACTOR_TODO.md` | TODO refactor frontend |
| `LGPD_IMPACT_REPORT.md` | Relatório de impacto LGPD |
| `MIGRATION_PHASE0.md` | Migração fase 0 (Flask→Django) |
| `PLATAFORMA-UNIFICADA.md` | Visão da plataforma unificada |
| `PRECOS-RM-SYSTEMS.md` | Tabela de preços |
| `READINESS_*.md` | 10+ readiness reports (arquitetura, billing, encryption, security, workers, etc.) |
| `ROPA.md` | Registro de operações de tratamento (LGPD) |
| `SECURITY_HARDENING_REPORT.md` | Relatório de hardening |
| `SUBOPERADORES-LGPD.md` | Suboperadores LGPD |
| `UI_*_REPORT.md` | Reports de UI (redesign, phase 2, phase 2c) |
| `BIMI_SETUP.md` | Configuração BIMI (logo no Gmail) |
| `commercial/` | Documentos comerciais |
| `internal/` | Documentos internos |
| `security/` | Documentos de segurança |

## 16. PADRÕES E CONVENÇÕES

### Código
- Idioma: português (nomes de variáveis, comentários, mensagens, templates)
- Django: class-based views + function views para APIs
- API: DRF ViewSets + Serializers + Permissions
- Frontend: Functional Components + Hooks + TypeScript
- CSS: Design System v2 (CSS custom properties + Tailwind)
- Migrations: sempre com `reverse_code` e comentários em português

### Segurança
- Senhas nunca em plaintext (Argon2 + criptografia)
- Tokens nunca em plaintext no banco (SHA-256 hash)
- CNPJ nunca exposto em claro na API
- Logs sanitizados (sem PII, senhas, tokens, IPs completos)
- Session binding: IP + user agent
- MFA obrigatório para admins (configurável)
- CSP nonce-based (sem unsafe-inline)
- Rate limit em múltiplas camadas

### LGPD
- Consentimento obrigatório antes de usar o sistema
- Documentos versionados (LEGAL_DOCUMENT_VERSION)
- Portal do titular (exportar, excluir, retificar)
- Encarregado (DPO) com contato visível
- Retenção definida por tipo de dado
- Cache de geocoding com hash (sem endereço completo)
---
*Documento gerado em 2026-07-01. Baseado na análise completa do código-fonte.*
