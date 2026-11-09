# READINESS — Migrations (Auditoria)

> **Modo:** READ ONLY  
> **Data:** 25/05/2026  
> **Comando:** `py manage.py showmigrations` (env CI temporário, SQLite local — **sem migrate executado**)

---

## 1. Resumo executivo

| Verificação | Resultado |
|-------------|-----------|
| Migrations duplicadas (mesmo app) | **NÃO ENCONTRADO** |
| Squashed migrations | **NÃO EXISTEM** |
| ReplaceMigration / forks | **NÃO ENCONTRADO** |
| Graph de dependências | **Linear e consistente** |
| Migration 0005 conflitante | **NÃO** — `auth.0005` ≠ `core.0005` (apps diferentes) |
| `core.0005_add_rm_superusers` perigosa em prod | **MITIGADA** — guards DEBUG + env flag |
| Divergência código vs banco local | **N/A** — `.env` ausente; ambiente auditoria usa SQLite vazio |
| Migration pendente conhecida | `core.0026_usersessionrecord_access_token` — validar em Neon/prod |

---

## 2. Inventário por app

### core (26 migrations)

```
0001_initial → 0002 slug → 0003 slug alter → 0004 fibramar seed
→ 0005 rm_superusers (RunPython) → 0006 flask fields → 0007 tickets
→ 0008-0013 indexes/notifications → 0014 LGPD → 0016 activation
→ 0018 CNPJ encrypt → 0019 audit → 0020-0023 renames/LGPD enterprise
→ 0022 sessions enterprise → 0024 plan quotas → 0025 billing
→ 0026 access_token session
```

### alerts (9 migrations)

```
0001 → 0008 encrypt telegram → 0009 worker status
```

### olt_ops (9 migrations)

```
0001 → 0005 encrypt sensitive → 0009 onu job queue
```

### ftth_viewer (7 migrations)

```
0001 → 0006 geocoding privacy
```

### Django/contrib

- `auth` 0001–0012, `admin`, `sessions`, `otp_*` — padrão django-otp

**Total arquivos migration custom:** 52 (confirmado glob)

---

## 3. CHECK 1 — Migration `core.0005_add_rm_superusers`

**Arquivo:** `core/migrations/0005_add_rm_superusers.py`

**Comportamento:**
```python
def create_rm_superusers(apps, schema_editor):
    if not getattr(settings, "DEBUG", False):
        return  # ← NÃO roda em produção
    if os.getenv("RM_SEED_SUPERUSERS", "").lower() not in ("1", "true", "yes", "on"):
        return  # ← exige flag explícita
    # cria superusers de RM_SEED_USER_{1-5}_*
```

**Classificação:** ✅ **SEGURO para produção** — no-op se `DEBUG=False`.

**Risco residual:** se alguém rodar `migrate` com `DEBUG=True` em staging e flags seed, cria superusers — operacional, não estrutural.

---

## 4. Migrations sensíveis (criptografia / LGPD / sessão)

| Migration | App | Risco | Nota |
|-----------|-----|-------|------|
| `0018_company_cnpj_encrypted_hash` | core | Médio | RunPython encrypt — depende `FIELD_ENCRYPTION_KEY` no migrate |
| `0020_*_encrypted_cnpj` | core | Baixo | Alter field para EncryptedCharField |
| `0008_encrypt_telegram_token` | alerts | Médio | RunPython encrypt tokens existentes |
| `0005_encrypt_sensitive_fields` | olt_ops | Médio | OLT + VPN passwords |
| `0022_security_enterprise` | core | Baixo | TrustedDevice, UserSessionRecord |
| `0026_usersessionrecord_access_token` | core | Baixo | AddField — **pendente validar em prod** |
| `0025_company_billing` | core | Baixo | Nova tabela billing |
| `0004_add_fibramar_company` | core | Operacional | Seed empresa demo |

---

## 5. Graph de dependências (core)

```
0001 → 0002 → 0003 → 0004 → 0005 → 0006 → 0007 → 0008 → 0009 → 0010
→ 0011 → 0012 → 0013 → 0014 → 0015 → 0016 → 0017 → 0018 → 0019 → 0020
→ 0021 → 0022 → 0023 → 0024 → 0025 → 0026
```

**Cross-app:**
- `olt_ops.0001` depende de `core` (Company FK)
- `alerts.0001` depende de `core.Company`
- `ftth_viewer.0003` make company required

**Sem ciclos detectados.**

---

## 6. Migrations duplicadas / órfãs

| Check | Resultado |
|-------|-----------|
| Dois `0005` no mesmo app | ❌ Não |
| Migration sem `dependencies` válida | ❌ Não |
| Arquivo migration sem `__init__.py` parent | ❌ Não |
| Número gap (ex: 0014→0016) | ✅ Normal — 0015 existe (rename index) |

---

## 7. `showmigrations` — ambiente auditoria

Executado com env CI (SECRET_KEY + SQLite + FIELD_ENCRYPTION_KEY teste):

**Resultado:** todas migrations `[ ]` não aplicadas — banco SQLite `audit_readonly.db` vazio (esperado).

**Implicação:** não foi possível comparar estado Neon/produção sem `.env` local do operador.

---

## 8. Riscos identificados

### Alto
- **`0026` não aplicada em produção** — se deploy recente incluiu sessões token-based, operadores devem confirmar `python manage.py showmigrations core` no ambiente real.

### Médio
- **RunPython encrypt migrations** — se rodadas com chave errada, dados ficam ilegíveis permanentemente até re-save.
- **Seed `0004 fibramar`** — empresa demo em todo migrate fresh; remover manualmente se indesejado.

### Baixo
- **Rename migrations** (0015, 0017, 0020, 0023) — só índices; sem alteração semântica.

---

## 9. Recomendações (não executadas)

1. Em staging/prod: `python manage.py showmigrations` e capturar output
2. Confirmar `core.0026` aplicada antes de usar access tokens de sessão
3. Nunca rodar `migrate` em prod com `DEBUG=True`
4. Backup antes de migrations RunPython de criptografia
5. Considerar squash futuro (dívida técnica, não blocker)

---

## 10. Classificação final

| Item | Status |
|------|--------|
| Graph consistente | ✅ OK |
| 0005 RM superusers | ✅ OK (guarded) |
| Forks/duplicatas | ✅ NÃO ENCONTRADO |
| Estado prod vs código | ⚠️ **NÃO VALIDADO** (sem .env/DB prod) |
| Blocker deploy | ⚠️ Confirmar 0026 em prod |

---

*Comandos destrutivos (migrate, fake, squash) não executados.*
