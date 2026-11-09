# Relatório de impacto LGPD — PASSO 3 Enterprise

**Data de referência:** 2026-05-23  
**Versão legal:** `LEGAL_DOCUMENT_VERSION` no `.env`

## Resumo executivo

O PASSO 3 implementa retenção automatizada, anonimização com hash irreversível, exportação ampliada (JSON/CSV/ZIP assinado), DSR com retries e comandos ROPA/DPIA. O score estimado sobe de ~81 para **88–92** em conformidade LGPD operacional (meta enterprise ≥90 após deploy + crons ativos).

## Controles implementados

| Controle | Antes | Depois |
|----------|-------|--------|
| Retenção global | Parcial | `purge_lgpd_retention` unificado |
| Consentimentos antigos | Sem purge | `CONSENT_RETENTION_DAYS` |
| Tickets fechados | PII indefinido | Anonimização após `TICKET_RETENTION_DAYS` |
| Export portabilidade | JSON básico | JSON + CSV + ZIP assinado + auditoria |
| DSR exclusão | Manual/script | Cron + retries + status `processing`/`failed` |
| ROPA | Documentação dispersa | `lgpd_data_inventory` + `lgpd_compliance_report` |

## Scores esperados (pós-deploy)

| Dimensão | Antes (auditoria) | Esperado |
|----------|-------------------|----------|
| LGPD operacional | ~81 | **88–92** |
| Segurança técnica | ~78 | **82–86** (com PASSO 1–2) |
| Enterprise target | — | **≥90** com crons + Redis + HMAC |

Gerar métricas atuais:

```bash
python manage.py lgpd_compliance_report --dpia --format json
python manage.py lgpd_data_inventory --format json --output logs/ropa.json
```

## Retenção configurável

| Variável | Default | Alvo |
|----------|---------|------|
| `CACHE_RETENTION_DAYS` | 90 | Geocoding + viabilidade |
| `AUDIT_RETENTION_DAYS` | 365 | `SecurityAuditEvent` |
| `CONSENT_RETENTION_DAYS` | 1825 | `ConsentRecord` |
| `DSR_RETENTION_DAYS` | 1825 | DSR concluídos |
| `TICKET_RETENTION_DAYS` | 730 | Tickets fechados |
| `OLT_LOG_RETENTION_DAYS` | 7 | `OnuCleanupJob.log_output` |
| `LGPD_EXPORT_TTL_HOURS` | 24 | ZIP export |

## Cron recomendado

```cron
# Retenção global — 04:00
0 4 * * * cd /var/www/saas && python manage.py purge_lgpd_retention

# DSR exclusão — 03:00
0 3 * * * cd /var/www/saas && python manage.py process_data_subject_requests --notify

# Relatório semanal
0 5 * * 1 cd /var/www/saas && python manage.py lgpd_compliance_report --dpia --output logs/lgpd-weekly.json
```

Scripts: `scripts/cron-lgpd-retention.sh`, `scripts/cron-lgpd-delete.sh`

## Riscos residuais

1. **Lat/lng em cache geocoding** — minimizado, mas ainda dado de localização; documentar na DPIA.
2. **Tokens Telegram** — criptografados em repouso; revisar exposição no payload do worker.
3. **DSR pendente >30d** — alerta no purge; exige processo humano.
4. **Produção sem Redis** — anti-replay bridge e rate limit degradados.

## Testes

```bash
python manage.py migrate
python manage.py test core.tests_lgpd_enterprise core.tests_phase3_security --keepdb
python manage.py purge_lgpd_retention --dry-run
```
