# Fase 0 — Fundação API (entregue)

## SSR intacto

Nenhuma rota/view SSR foi removida. `FRONTEND_MODE=hybrid` (padrão) mantém convivência.

## Rotas `/api/v1/` (novas e existentes)

### Auth (`/api/v1/auth/`)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `login/` | Login → JWT + `needs_mfa` |
| POST | `mfa/verify/` | TOTP → `mfa_verified=true` |
| POST | `mfa/setup/` | Inicia/confirma setup TOTP + QR |
| POST | `mfa/recovery/` | Regenera backup codes |
| POST | `token/refresh/` | Refresh rotativo (blacklist) |
| POST | `refresh/` | Alias legado → mesmo handler |
| POST | `logout/` | Blacklist refresh |
| POST | `change-password/` | Troca obrigatória |
| POST | `activate/` | Ativação por link |
| POST | `password-reset/` | Solicita e-mail |
| POST | `password-reset/confirm/` | Confirma nova senha |
| GET/DELETE | `trusted-devices/` | Dispositivos MFA confiáveis |
| GET/DELETE | `sessions/` | Sessões Django + refresh JWT |

### Contexto

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `me/` | Perfil + permissões + módulos |
| GET | `companies/me/` | Tenant atual (JWT / `X-Company-Slug`) |
| GET | `companies/{slug}/` | Tenant por slug explícito |

### FTTH v1 (wrappers — lógica legada inalterada)

| Legado (SSR) | Novo (JWT) |
|--------------|------------|
| `/{slug}/verificador/api/arquivos` | `GET /api/v1/companies/{slug}/ftth/arquivos` |
| `.../coordenadas` | `.../ftth/coordenadas` |
| `.../contar-pontos` | `.../ftth/contar-pontos` |
| `.../geocode` | `.../ftth/geocode` |
| `.../cep` | `.../ftth/cep` |
| `.../geocode/suggestions` | `.../ftth/geocode/suggestions` |
| `.../verificar-viabilidade` | `.../ftth/verificar-viabilidade` |
| `.../cache/geocoding/stats` | `.../ftth/cache/geocoding/stats` |
| `.../cache/geocoding/clear` | `.../ftth/cache/geocoding/clear` |
| `.../adicionar-cto` | `.../ftth/adicionar-cto` |
| `.../remover-cto` | `.../ftth/remover-cto` |

Rotas legadas **permanecem ativas** (sem redirect HTTP — APIs POST não suportam 301).

### Admin API (já existia)

- `companies/`, `maps/`, `users/` (ViewSets)
- `schema/`, `docs/` (Swagger)

## SIMPLE_JWT (`settings.py`)

```python
ACCESS_TOKEN_LIFETIME = 15 min   # JWT_ACCESS_MINUTES
REFRESH_TOKEN_LIFETIME = 7 days  # JWT_REFRESH_DAYS
ROTATE_REFRESH_TOKENS = True
BLACKLIST_AFTER_ROTATION = True
```

## Claims do access token

| Claim | Descrição |
|-------|-----------|
| `user_id` | PK do usuário |
| `role` | RM / COMPANY_ADMIN / COMPANY_USER |
| `is_rm_admin` | bool |
| `is_company_admin` | bool |
| `company_slug` | slug do tenant (se houver) |
| `plan_code` | plano da empresa |
| `enabled_modules` | `["verificador","alertas","olt"]` |
| `mfa_verified` | **false** até TOTP válido |
| `must_change_password` | bool |

## Fluxo MFA

```
1. POST /auth/login/  (user+senha OK, MFA habilitado)
   → access/refresh com mfa_verified=false
   → needs_mfa=true
   → mfa_pending_token (opcional, curto)

2. POST /auth/mfa/verify/  { token, mfa_pending_token? }
   → novos tokens com mfa_verified=true

3. GET /me/ ou /companies/me/
   → RequireMfaVerified bloqueia se mfa_verified=false
```

Usuário com MFA obrigatório mas **sem TOTP configurado** recebe `needs_mfa_setup=true`.

## CORS + CSP

- `CORS_ALLOWED_ORIGINS` — incluir `http://localhost:5173`
- Headers: `Authorization`, `X-Company-Slug`
- `CSP_CONNECT_EXTRA_HOSTS` — mesma origem da SPA em `connect-src`

## Variáveis de ambiente

```env
FRONTEND_MODE=hybrid
FRONTEND_URL=http://localhost:5173
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
CSP_CONNECT_EXTRA_HOSTS=http://localhost:5173,http://127.0.0.1:5173
CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
JWT_ACCESS_MINUTES=15
JWT_REFRESH_DAYS=7
```

## Swagger

Documentação em `/api/v1/docs/` (drf-spectacular). Endpoints auth expostos automaticamente.
