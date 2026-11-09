# Etapa 4 — API security e hardening

**Status:** concluída (aguardando sua aprovação para Etapa 5).

## Objetivo

Reduzir vazamento de informação em respostas JSON, webhooks e health checks, sem alterar regras de negócio.

## Vulnerabilidades tratadas

| ID | Severidade | Problema | Correção |
|----|------------|----------|----------|
| E4-1 | HIGH | Path disclosure em `api_arquivos` (`caminho` com path absoluto) | Campo removido; cliente usa `id` (map_id) |
| E4-2 | HIGH | Path em erro 404 (`caminho_esperado`) | Só em `DEBUG=True` |
| E4-3 | MED | Exceções em JSON (`str(e)`, `tipo`) | `core/json_responses.py` + uso em `ftth_viewer/views.py` |
| E4-4 | MED | DRF 500 sem handler | `core/drf_exception_handler.py` em `REST_FRAMEWORK` |
| E4-5 | HIGH | Token Asaas via query string | Rejeitado; só header `asaas-access-token` / `X-Asaas-Token` |
| E4-6 | LOW | Webhook sem token configurado aceitava tentativas | HTTP 503 se `ASAAS_WEBHOOK_TOKEN` vazio |
| E4-7 | LOW | Resposta webhook expõe `company` slug | Detalhes só em `DEBUG` |
| E4-8 | MED | `/health/security/` público | Opcional: `HEALTH_SECURITY_ALLOWED_IPS` |
| E4-9 | LOW | `/ready/` vazava `str(exc)` do DB | Mensagem genérica em produção |

| E4-10 | LOW | SQLite em testes recebia `sslmode`/`connect_timeout` de Postgres | `requires_ssl` e `OPTIONS` só para URLs PostgreSQL |

## Arquivos alterados

- `core/json_responses.py` (novo)
- `core/drf_exception_handler.py` (novo)
- `core/tests_security_api.py` (novo)
- `core/billing/asaas_webhook.py`
- `core/health_views.py`
- `core/views.py` (exclusão de empresa — mensagem 500 genérica)
- `ftth_viewer/views.py`
- `saas_viabilidade/settings.py` (`EXCEPTION_HANDLER`, `HEALTH_SECURITY_ALLOWED_IPS`)

## Configuração recomendada (produção)

```env
# Webhook Asaas — configure no painel Asaas apenas via header, nunca ?token=
ASAAS_WEBHOOK_TOKEN=<segredo-longo>

# Restringir auditoria de segurança (opcional; vazio = comportamento anterior)
HEALTH_SECURITY_ALLOWED_IPS=127.0.0.1,::1
```

URL do webhook: `https://<dominio>/api/webhooks/asaas/` com header `asaas-access-token`.

## Testes

```powershell
$env:DATABASE_URL="sqlite:///:memory:"
$env:SECRET_KEY="test-secret-key-min-50-chars-for-django-settings-xx"
$env:FIELD_ENCRYPTION_KEY="<chave-fernet-valida>"
python manage.py test core.tests_security_api core.tests_security_secrets core.tests_security_auth core.tests_security_authorization -v2
```

## Regressões esperadas

- Integrações Asaas que enviavam `?token=` no URL **deixam de funcionar** — migrar para header.
- Clientes que dependiam de `caminho` em `/api/arquivos` devem usar `id` (já era o padrão no frontend).
- Monitoramento externo em `/health/security/` precisa de IP na allowlist ou deixar variável vazia.

## Próximo passo

**Etapa 5** — CI/CD: `pip-audit`/`bandit` bloqueantes, `security-check.sh`, Docker/nginx.
