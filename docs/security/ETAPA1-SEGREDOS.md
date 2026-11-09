# Etapa 1 — Segredos e configuração crítica

## Vulnerabilidades corrigidas

| ID | Problema | Status |
|----|----------|--------|
| CRITICAL-01 | `.env` versionado no Git | `.env` removido do índice; `.gitignore` atualizado |
| MEDIUM-16 | Fallback Fernet silencioso via `SECRET_KEY` | Removido por padrão; opt-in explícito |
| — | `.env.example` com `SECRET_KEY` insegura padrão | Placeholders vazios + instruções |
| — | Validação fraca de `FIELD_ENCRYPTION_KEY` | Validação Fernet no bootstrap e `check_security` |

---

## Checklist de rotação de segredos (ação manual)

Após remover `.env` do histórico Git, **rotacione** (ordem sugerida):

- [ ] `SECRET_KEY` — invalida sessões existentes
- [ ] `FIELD_ENCRYPTION_KEY` — **re-salvar** no painel: tokens Telegram, senhas OLT/VPN (dados antigos exigem chave anterior ou migração)
- [ ] `RESEND_API_KEY`
- [ ] `OPENROUTESERVICE_API_KEY`
- [ ] `ASAAS_API_KEY` / `ASAAS_WEBHOOK_TOKEN`
- [ ] `ALERT_BRIDGE_API_TOKEN` + `BRIDGE_HMAC_SECRET`
- [ ] `DATABASE_URL` (senha do banco) — se o repo foi exposto publicamente
- [ ] `CNPJ_HASH_SALT`, `GEOCODING_CACHE_SALT` — se comprometidos
- [ ] Credenciais SMTP (`EMAIL_HOST_PASSWORD`) se usadas

### Histórico Git

Se o repositório foi compartilhado ou público:

```bash
# Ver se .env já foi commitado
git log --oneline -- .env

# Purge do histórico (coordene com a equipe)
# git filter-repo --path .env --invert-paths
```

---

## Variáveis obrigatórias

### Produção / VPS (`DJANGO_ENV=production` ou `VPS_ENVIRONMENT=true`)

| Variável | Obrigatória | Notas |
|----------|:-----------:|-------|
| `SECRET_KEY` | Sim | ≥50 caracteres; não usar valores da blocklist |
| `DATABASE_URL` | Sim | PostgreSQL com SSL quando remoto |
| `ALLOWED_HOSTS` | Sim | Domínios explícitos, sem `*` |
| `FIELD_ENCRYPTION_KEY` | Sim | Fernet 44 chars (`setup_p1_security --write-key`) |
| `BRIDGE_HMAC_SECRET` | Sim | ≠ `ALERT_BRIDGE_API_TOKEN` |
| `ALERT_BRIDGE_API_TOKEN` | Sim | Token longo aleatório |
| `DEBUG` | Não (deve ser `False`) | Boot falha se `True` |

### Desenvolvimento local

| Variável | Obrigatória | Notas |
|----------|:-----------:|-------|
| `SECRET_KEY` | Sim | `python manage.py check_security --generate-secret-key` |
| `DATABASE_URL` | Sim | |
| `FIELD_ENCRYPTION_KEY` | Sim* | *Ou `ALLOW_FIELD_ENCRYPTION_SECRET_FALLBACK=true` (não usar em prod) |

### Recomendadas em produção

`CNPJ_HASH_SALT`, `REDIS_URL`, `GEOCODING_CACHE_SALT`, `DPO_EMAIL`, `CSRF_TRUSTED_ORIGINS`

---

## Arquivos modificados

| Arquivo | Alteração |
|---------|-----------|
| `.gitignore` | Ignora `.env`; mantém `.env.example` |
| `.env` | Removido do índice Git (`git rm --cached`) |
| `.env.example` | Sem segredos padrão; instruções de geração |
| `saas_viabilidade/security_bootstrap.py` | Validação `FIELD_ENCRYPTION_KEY` no boot |
| `core/field_encryption.py` | Sem fallback silencioso; opt-in explícito |
| `saas_viabilidade/env_validation.py` | Valida força da chave Fernet |
| `core/management/commands/check_security.py` | Checagem Fernet |
| `core/tests_security_secrets.py` | Testes novos |
| `.github/workflows/security.yml` | Chave Fernet CI válida |
| `.github/workflows/tests.yml` | Idem |

---

## Comandos úteis

```bash
# Copiar modelo de ambiente
cp .env.example .env

# Gerar SECRET_KEY
python manage.py check_security --generate-secret-key

# Gerar e gravar FIELD_ENCRYPTION_KEY no .env
python manage.py setup_p1_security --write-key

# Auditoria local
python manage.py check_security --strict
bash scripts/security-check.sh
```

---

## Diff resumido (comportamento)

1. **Git**: `.env` deixa de ser rastreado; arquivo local preservado.
2. **Boot**: produção e dev exigem `FIELD_ENCRYPTION_KEY` válida, exceto testes (`manage.py test`).
3. **Criptografia**: `encrypt_value` falha sem chave; derivação de `SECRET_KEY` só com `ALLOW_FIELD_ENCRYPTION_SECRET_FALLBACK=true` em `DEBUG` não-produção, ou em testes.
4. **Compatibilidade**: dados já criptografados com chave antiga ainda descriptografam se a mesma `FIELD_ENCRYPTION_KEY` (ou fallback legado explícito) estiver configurada.

---

*Etapa 2 (autenticação/login) aguarda aprovação antes de iniciar.*
