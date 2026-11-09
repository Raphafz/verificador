# Rotação de secrets — runbook

Use este guia se `.env`, logs ou fork expuseram credenciais.

## Ordem recomendada

1. **PostgreSQL (Neon / VPS)** — rotacionar senha do usuário da aplicação; atualizar `DATABASE_URL`; reiniciar Gunicorn.
2. **`SECRET_KEY`** — gerar nova chave; reiniciar app (sessões antigas expiram).
3. **`FIELD_ENCRYPTION_KEY`** — **crítico**: dados criptografados (CNPJ, tokens Telegram, senhas OLT/VPN) ficam ilegíveis se a chave mudar sem re-encrypt. Só rotacione com plano de migração ou se a chave nunca foi usada em produção.
4. **Alert-bridge** — gerar novo par com `python manage.py shell`:

```python
from core.bridge_security import generate_bridge_credentials
token, hmac_secret = generate_bridge_credentials()
print("ALERT_BRIDGE_API_TOKEN=", token)
print("BRIDGE_HMAC_SECRET=", hmac_secret)
```

Atualizar `.env` do Django **e** do worker Node; reiniciar ambos.

5. **`ASAAS_WEBHOOK_TOKEN`** — novo token no painel Asaas + `.env`; URL: `https://seu-dominio/api/webhooks/asaas/?token=...`
6. **`ASAAS_API_KEY`** — revogar chave antiga no Asaas; criar restrita se possível.
7. **Redis** — `REDIS_URL` com senha nova se aplicável.

## Verificação pós-rotação

```bash
python manage.py check --deploy
python manage.py check_bridge_health
curl -s https://seu-dominio/health/
```

## Prevenção

- Nunca commitar `.env` em repositório público.
- CI: usar secrets do GitHub, não valores reais.
- Logs: mascarar tokens (já aplicado em bridge HMAC).
