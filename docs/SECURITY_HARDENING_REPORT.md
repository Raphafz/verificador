# Relatório de hardening — PASSO 4 Enterprise

**Data:** 2026-05-23

## Score de segurança (estimado)

| Dimensão | Antes (PASSO 1–3) | Após PASSO 4 |
|----------|-------------------|--------------|
| **Segurança técnica** | 82–86 | **88–93** |
| **LGPD** | 88–92 | 88–92 |
| **Meta enterprise** | — | **≥90** com Redis + CSP strict + MFA |

```bash
python manage.py check_security --deploy --strict
curl -s http://127.0.0.1:8000/health/security/
```

## 1. CSP Strict

| Controle | Status |
|----------|--------|
| Nonce por request | `CspNonceMiddleware` |
| `strict-dynamic` scripts | `CSP_STRICT=True` |
| Sem `unsafe-inline` em scripts (strict) | `security_headers.py` |
| Styles com nonce (strict) | `style-src 'nonce-…'` |
| Compatibilidade onclick | `static/js/csp-actions.js` + `data-csp-action` |

## 2. MFA Enterprise

| Controle | Status |
|----------|--------|
| TOTP + backup codes | `django_otp` |
| Remember device | Cookie `mfa_trust` + `TrustedDevice` |
| Revogar dispositivos | `/rm/mfa/devices/` |
| Lockout MFA | `core/mfa_lockout.py` |
| Recovery | `/rm/mfa/recovery/` |
| Admin enforcement | `MFA_REQUIRED` + `MfaEnforcementMiddleware` |

## 3. Sessões

| Controle | Status |
|----------|--------|
| Rotação no login | `session_security.rotate_session` |
| Limite concorrente | `SESSION_MAX_CONCURRENT` (default 3) |
| Idle timeout | `SessionIdleTimeoutMiddleware` |
| Revogação | `/rm/sessoes/` |
| Login suspeito | `suspicious_login` audit event |

## 4. Rate limit

| Controle | Status |
|----------|--------|
| Login lockout progressivo | `login_lockout.py` |
| Global middleware | `GlobalRateLimitMiddleware` |
| DRF throttling | `core/throttling.py` |
| Redis backend | `REDIS_URL` → `CACHES` |

## 5. Upload

| Controle | Status |
|----------|--------|
| Nomes aleatórios | `secure_upload_filename` |
| MIME / magic | `SecureFileValidator` |
| Quarentena | `quarantine_file` |
| ClamAV hook | `UPLOAD_ANTIVIRUS_ENABLED` |
| Strip metadata | `strip_file_metadata` (Office) |

## 6. DevSecOps

| Artefato | Caminho |
|----------|---------|
| CI security | `.github/workflows/security.yml` |
| Pre-commit | `.pre-commit-config.yaml` |
| Scan local | `scripts/security-check.sh` |
| Gunicorn | `docs/deploy/gunicorn.conf.py.example` |
| Redis | `docs/deploy/redis.conf.example` |
| Nginx | `docs/deploy/nginx-alert-bridge.conf.example` |

## Variáveis `.env` (PASSO 4)

```env
CSP_STRICT=true
MFA_REQUIRED=true
MFA_REQUIRED_COMPANY_ADMINS=false
MFA_REMEMBER_DAYS=30
SESSION_MAX_CONCURRENT=3
SESSION_IDLE_TIMEOUT=1800
REDIS_URL=redis://127.0.0.1:6379/1
FORCE_RATE_LIMIT=false
DRF_THROTTLE_BURST=60/min
DRF_THROTTLE_SUSTAINED=2000/hour
UPLOAD_ANTIVIRUS_ENABLED=false
```

## Migration

```bash
python manage.py migrate core 0022
```

## Testes

```bash
python manage.py test core.tests_phase4_security --keepdb
```
